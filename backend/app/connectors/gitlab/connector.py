"""
GitLab Connector — first Axis integration plugin.

Implements BaseConnector to ingest GitLab project data:
- Issues + comments
- Merge Requests + comments
- Commits
- Milestones

Normalizes everything into NormalizedEvent format for storage/embedding.
"""

import hashlib
import hmac
import secrets
from datetime import datetime
from urllib.parse import urlencode

import httpx
from dateutil.parser import isoparse

from app.config import settings
from app.connectors.base import BaseConnector, ConnectorInfo, NormalizedEvent
from app.connectors.gitlab.client import GitLabClient


class GitLabConnector(BaseConnector):
    """GitLab integration for Axis."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            type="gitlab",
            display_name="GitLab",
            description="Connect to GitLab projects to ingest issues, merge requests, commits, and discussions.",
            icon="gitlab",
            auth_type="oauth2",
            config_schema={
                "type": "object",
                "required": ["gitlab_project_id"],
                "properties": {
                    "gitlab_project_id": {
                        "type": "integer",
                        "description": "The GitLab project ID to sync",
                    },
                    "gitlab_url": {
                        "type": "string",
                        "description": "GitLab instance URL (default: https://gitlab.com)",
                        "default": "https://gitlab.com",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Project namespace (e.g., 'org/repo')",
                    },
                },
            },
        )

    async def validate_config(self, config: dict) -> bool:
        """Check if the GitLab project exists and is accessible."""
        # Validation requires a token, so this is a basic schema check
        return "gitlab_project_id" in config

    async def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        """Build the GitLab OAuth2 authorization URL."""
        params = {
            "client_id": settings.gitlab_app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": "read_user read_api read_repository",
        }
        return f"{settings.gitlab_url}/oauth/authorize?{urlencode(params)}"

    async def exchange_oauth_code(
        self, code: str, redirect_uri: str
    ) -> dict | None:
        """Exchange OAuth code for access + refresh tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.gitlab_url}/oauth/token",
                data={
                    "client_id": settings.gitlab_app_id,
                    "client_secret": settings.gitlab_app_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if resp.status_code == 200:
                return resp.json()
        return None

    async def sync_all(
        self,
        config: dict,
        access_token: str,
        since: datetime | None = None,
    ) -> list[NormalizedEvent]:
        """
        Full project sync — fetches all issues, MRs, commits, and their comments.
        Returns a flat list of NormalizedEvents.
        """
        project_id = config["gitlab_project_id"]
        gitlab_url = config.get("gitlab_url", settings.gitlab_url)
        events: list[NormalizedEvent] = []

        async with GitLabClient(access_token, gitlab_url) as client:
            # --- Issues ---
            issues = await client.get_issues(project_id, since=since)
            for issue in issues:
                events.append(self._normalize_issue(issue, gitlab_url))

                # Fetch comments for each issue
                notes = await client.get_issue_notes(project_id, issue["iid"])
                for note in notes:
                    if note.get("system", False):
                        continue  # Skip system notes (label changes, etc.)
                    events.append(
                        self._normalize_note(note, issue, "issue", gitlab_url)
                    )

            # --- Merge Requests ---
            mrs = await client.get_merge_requests(project_id, since=since)
            for mr in mrs:
                events.append(self._normalize_mr(mr, gitlab_url))

                # Fetch comments for each MR
                notes = await client.get_mr_notes(project_id, mr["iid"])
                for note in notes:
                    if note.get("system", False):
                        continue
                    events.append(
                        self._normalize_note(note, mr, "merge_request", gitlab_url)
                    )

            # --- Commits ---
            commits = await client.get_commits(project_id, since=since)
            for commit in commits:
                events.append(self._normalize_commit(commit, project_id, gitlab_url))

            # --- Milestones ---
            milestones = await client.get_milestones(project_id)
            for ms in milestones:
                events.append(self._normalize_milestone(ms, project_id, gitlab_url))

        return events

    def handle_webhook(
        self,
        payload: dict,
        headers: dict,
        webhook_secret: str | None = None,
    ) -> list[NormalizedEvent] | None:
        """Process a GitLab webhook event."""
        # Verify webhook token
        if webhook_secret:
            token = headers.get("x-gitlab-token", "")
            if token != webhook_secret:
                return None

        object_kind = payload.get("object_kind")

        if object_kind == "issue":
            issue = payload.get("object_attributes", {})
            return [self._normalize_issue_webhook(payload)]

        elif object_kind == "merge_request":
            return [self._normalize_mr_webhook(payload)]

        elif object_kind == "note":
            return [self._normalize_note_webhook(payload)]

        elif object_kind == "push":
            events = []
            for commit in payload.get("commits", []):
                events.append(self._normalize_commit_webhook(commit, payload))
            return events if events else None

        return None

    def get_event_types(self) -> list[str]:
        return [
            "issue.created",
            "issue.updated",
            "issue.closed",
            "issue.commented",
            "merge_request.opened",
            "merge_request.updated",
            "merge_request.merged",
            "merge_request.closed",
            "merge_request.commented",
            "commit.pushed",
            "milestone.created",
            "milestone.updated",
        ]

    async def setup_webhook(
        self,
        config: dict,
        access_token: str,
        webhook_url: str,
        webhook_secret: str,
    ) -> bool:
        """Register a webhook on the GitLab project."""
        project_id = config["gitlab_project_id"]
        gitlab_url = config.get("gitlab_url", settings.gitlab_url)

        async with GitLabClient(access_token, gitlab_url) as client:
            try:
                await client.create_webhook(
                    project_id, webhook_url, webhook_secret
                )
                return True
            except Exception as e:
                print(f"Failed to create GitLab webhook: {e}")
                return False

    # ── Normalizers ─────────────────────────────────────────────

    def _normalize_issue(self, issue: dict, gitlab_url: str) -> NormalizedEvent:
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"issue:{issue['id']}",
            source_url=issue.get("web_url"),
            event_type=f"issue.{_state_to_event(issue.get('state', 'opened'))}",
            title=issue.get("title"),
            content=issue.get("description"),
            actor_name=issue.get("author", {}).get("name"),
            actor_email=issue.get("author", {}).get("email"),
            source_timestamp=_parse_dt(issue.get("updated_at") or issue.get("created_at")),
            extra={
                "iid": issue.get("iid"),
                "state": issue.get("state"),
                "labels": [l for l in issue.get("labels", [])],
                "milestone": issue.get("milestone", {}).get("title") if issue.get("milestone") else None,
                "assignees": [a.get("name") for a in issue.get("assignees", [])],
                "weight": issue.get("weight"),
                "confidential": issue.get("confidential", False),
            },
        )

    def _normalize_mr(self, mr: dict, gitlab_url: str) -> NormalizedEvent:
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"merge_request:{mr['id']}",
            source_url=mr.get("web_url"),
            event_type=f"merge_request.{_mr_state_to_event(mr.get('state', 'opened'))}",
            title=mr.get("title"),
            content=mr.get("description"),
            actor_name=mr.get("author", {}).get("name"),
            actor_email=mr.get("author", {}).get("email"),
            source_timestamp=_parse_dt(mr.get("updated_at") or mr.get("created_at")),
            extra={
                "iid": mr.get("iid"),
                "state": mr.get("state"),
                "source_branch": mr.get("source_branch"),
                "target_branch": mr.get("target_branch"),
                "labels": mr.get("labels", []),
                "milestone": mr.get("milestone", {}).get("title") if mr.get("milestone") else None,
                "reviewers": [r.get("name") for r in mr.get("reviewers", [])],
                "merged_by": mr.get("merged_by", {}).get("name") if mr.get("merged_by") else None,
            },
        )

    def _normalize_note(
        self, note: dict, parent: dict, parent_type: str, gitlab_url: str
    ) -> NormalizedEvent:
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"note:{note['id']}",
            source_url=f"{parent.get('web_url')}#note_{note['id']}",
            event_type=f"{parent_type}.commented",
            title=f"Comment on {parent_type.replace('_', ' ')} #{parent.get('iid')}: {parent.get('title', '')}",
            content=note.get("body"),
            actor_name=note.get("author", {}).get("name"),
            actor_email=note.get("author", {}).get("email"),
            source_timestamp=_parse_dt(note.get("updated_at") or note.get("created_at")),
            extra={
                "parent_type": parent_type,
                "parent_iid": parent.get("iid"),
                "parent_title": parent.get("title"),
                "resolvable": note.get("resolvable", False),
                "resolved": note.get("resolved", False),
            },
        )

    def _normalize_commit(
        self, commit: dict, project_id: int, gitlab_url: str
    ) -> NormalizedEvent:
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"commit:{commit['id']}",
            source_url=commit.get("web_url"),
            event_type="commit.pushed",
            title=commit.get("title"),
            content=commit.get("message"),
            actor_name=commit.get("author_name"),
            actor_email=commit.get("author_email"),
            source_timestamp=_parse_dt(commit.get("committed_date") or commit.get("created_at")),
            extra={
                "short_id": commit.get("short_id"),
                "stats": commit.get("stats", {}),
            },
        )

    def _normalize_milestone(
        self, ms: dict, project_id: int, gitlab_url: str
    ) -> NormalizedEvent:
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"milestone:{ms['id']}",
            source_url=ms.get("web_url"),
            event_type="milestone.created",
            title=ms.get("title"),
            content=ms.get("description"),
            actor_name=None,
            actor_email=None,
            source_timestamp=_parse_dt(ms.get("updated_at") or ms.get("created_at")),
            extra={
                "state": ms.get("state"),
                "due_date": ms.get("due_date"),
                "start_date": ms.get("start_date"),
            },
        )

    # ── Webhook normalizers ────────────────────────────────────

    def _normalize_issue_webhook(self, payload: dict) -> NormalizedEvent:
        attrs = payload.get("object_attributes", {})
        user = payload.get("user", {})
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"issue:{attrs['id']}",
            source_url=attrs.get("url"),
            event_type=f"issue.{attrs.get('action', 'updated')}",
            title=attrs.get("title"),
            content=attrs.get("description"),
            actor_name=user.get("name"),
            actor_email=user.get("email"),
            source_timestamp=_parse_dt(attrs.get("updated_at")),
            extra={
                "iid": attrs.get("iid"),
                "state": attrs.get("state"),
                "action": attrs.get("action"),
                "labels": [l.get("title") for l in payload.get("labels", [])],
            },
        )

    def _normalize_mr_webhook(self, payload: dict) -> NormalizedEvent:
        attrs = payload.get("object_attributes", {})
        user = payload.get("user", {})
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"merge_request:{attrs['id']}",
            source_url=attrs.get("url"),
            event_type=f"merge_request.{attrs.get('action', 'updated')}",
            title=attrs.get("title"),
            content=attrs.get("description"),
            actor_name=user.get("name"),
            actor_email=user.get("email"),
            source_timestamp=_parse_dt(attrs.get("updated_at")),
            extra={
                "iid": attrs.get("iid"),
                "state": attrs.get("state"),
                "action": attrs.get("action"),
                "source_branch": attrs.get("source_branch"),
                "target_branch": attrs.get("target_branch"),
            },
        )

    def _normalize_note_webhook(self, payload: dict) -> NormalizedEvent:
        attrs = payload.get("object_attributes", {})
        user = payload.get("user", {})
        noteable_type = attrs.get("noteable_type", "").lower()
        parent_type = "issue" if "issue" in noteable_type else "merge_request"
        parent = payload.get(parent_type, {})
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"note:{attrs['id']}",
            source_url=attrs.get("url"),
            event_type=f"{parent_type}.commented",
            title=f"Comment on {parent.get('title', 'unknown')}",
            content=attrs.get("note"),
            actor_name=user.get("name"),
            actor_email=user.get("email"),
            source_timestamp=_parse_dt(attrs.get("updated_at")),
            extra={
                "parent_type": parent_type,
                "parent_iid": parent.get("iid"),
                "noteable_type": attrs.get("noteable_type"),
            },
        )

    def _normalize_commit_webhook(
        self, commit: dict, payload: dict
    ) -> NormalizedEvent:
        return NormalizedEvent(
            connector_type="gitlab",
            source_id=f"commit:{commit['id']}",
            source_url=commit.get("url"),
            event_type="commit.pushed",
            title=commit.get("title"),
            content=commit.get("message"),
            actor_name=commit.get("author", {}).get("name"),
            actor_email=commit.get("author", {}).get("email"),
            source_timestamp=_parse_dt(commit.get("timestamp")),
            extra={
                "added": commit.get("added", []),
                "modified": commit.get("modified", []),
                "removed": commit.get("removed", []),
                "ref": payload.get("ref"),
            },
        )


# ── Helpers ─────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime:
    """Parse an ISO datetime string, falling back to now()."""
    if value:
        try:
            return isoparse(value)
        except (ValueError, TypeError):
            pass
    return datetime.utcnow()


def _state_to_event(state: str) -> str:
    """Map GitLab issue state to event action."""
    return {"opened": "created", "closed": "closed", "reopened": "updated"}.get(
        state, "updated"
    )


def _mr_state_to_event(state: str) -> str:
    """Map GitLab MR state to event action."""
    return {
        "opened": "opened",
        "closed": "closed",
        "merged": "merged",
        "locked": "updated",
    }.get(state, "updated")
