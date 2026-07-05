"""
GitLab API client — handles bulk data fetching with pagination.

This is the 'heavy lifting' layer for the initial project sync.
For AI agent queries at runtime, we'll use the GitLab MCP server instead.
"""

import asyncio
from datetime import datetime

import httpx

from app.config import settings


class GitLabClient:
    """Async GitLab API client for bulk data operations."""

    def __init__(self, access_token: str, gitlab_url: str | None = None):
        self.base_url = (gitlab_url or settings.gitlab_url).rstrip("/")
        self.api_url = f"{self.base_url}/api/v4"
        if access_token.startswith("glpat-"):
            self.headers = {"PRIVATE-TOKEN": access_token}
        else:
            self.headers = {"Authorization": f"Bearer {access_token}"}
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Pagination helper ──────────────────────────────────────

    async def _paginate(
        self, endpoint: str, params: dict | None = None
    ) -> list[dict]:
        """Fetch all pages of a paginated GitLab API endpoint."""
        results = []
        params = params or {}
        params.setdefault("per_page", 100)
        page = 1

        while True:
            params["page"] = page
            resp = await self._client.get(
                f"{self.api_url}{endpoint}", params=params
            )
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            results.extend(data)

            # Check if there are more pages
            total_pages = int(resp.headers.get("x-total-pages", 1))
            if page >= total_pages:
                break
            page += 1

        return results

    # ── Project ─────────────────────────────────────────────────

    async def get_project(self, project_id: int) -> dict:
        """Fetch a single project's details."""
        resp = await self._client.get(f"{self.api_url}/projects/{project_id}")
        resp.raise_for_status()
        return resp.json()

    async def search_projects(self, query: str) -> list[dict]:
        """Search for projects by name."""
        return await self._paginate(
            "/projects", params={"search": query, "membership": True}
        )

    # ── Issues ──────────────────────────────────────────────────

    async def get_issues(
        self, project_id: int, since: datetime | None = None
    ) -> list[dict]:
        """Fetch all issues for a project."""
        params = {"state": "all", "scope": "all", "order_by": "updated_at"}
        if since:
            params["updated_after"] = since.isoformat()
        return await self._paginate(
            f"/projects/{project_id}/issues", params=params
        )

    async def get_issue_notes(
        self, project_id: int, issue_iid: int
    ) -> list[dict]:
        """Fetch all comments/notes on an issue."""
        return await self._paginate(
            f"/projects/{project_id}/issues/{issue_iid}/notes",
            params={"sort": "asc"},
        )

    # ── Merge Requests ──────────────────────────────────────────

    async def get_merge_requests(
        self, project_id: int, since: datetime | None = None
    ) -> list[dict]:
        """Fetch all merge requests for a project."""
        params = {"state": "all", "scope": "all", "order_by": "updated_at"}
        if since:
            params["updated_after"] = since.isoformat()
        return await self._paginate(
            f"/projects/{project_id}/merge_requests", params=params
        )

    async def get_mr_notes(
        self, project_id: int, mr_iid: int
    ) -> list[dict]:
        """Fetch all comments/notes on a merge request."""
        return await self._paginate(
            f"/projects/{project_id}/merge_requests/{mr_iid}/notes",
            params={"sort": "asc"},
        )

    # ── Commits ─────────────────────────────────────────────────

    async def get_commits(
        self, project_id: int, since: datetime | None = None
    ) -> list[dict]:
        """Fetch commits (default branch)."""
        params = {"with_stats": True}
        if since:
            params["since"] = since.isoformat()
        return await self._paginate(
            f"/projects/{project_id}/repository/commits", params=params
        )

    # ── Milestones ──────────────────────────────────────────────

    async def get_milestones(self, project_id: int) -> list[dict]:
        """Fetch all milestones for a project."""
        return await self._paginate(
            f"/projects/{project_id}/milestones",
            params={"state": "active"},
        )

    # ── Labels ──────────────────────────────────────────────────

    async def get_labels(self, project_id: int) -> list[dict]:
        """Fetch all labels for a project."""
        return await self._paginate(f"/projects/{project_id}/labels")

    # ── Webhooks ────────────────────────────────────────────────

    async def create_webhook(
        self,
        project_id: int,
        url: str,
        secret: str,
        events: list[str] | None = None,
    ) -> dict:
        """Register a webhook on the GitLab project."""
        payload = {
            "url": url,
            "token": secret,
            "push_events": True,
            "issues_events": True,
            "merge_requests_events": True,
            "note_events": True,
            "pipeline_events": False,
            "enable_ssl_verification": True,
        }
        resp = await self._client.post(
            f"{self.api_url}/projects/{project_id}/hooks", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    # ── User Info ───────────────────────────────────────────────

    async def get_current_user(self) -> dict:
        """Fetch the authenticated user's profile."""
        resp = await self._client.get(f"{self.api_url}/user")
        resp.raise_for_status()
        return resp.json()
