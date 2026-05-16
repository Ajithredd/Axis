"""Axis — GitLab service for deep project interaction."""

import gitlab
from typing import List, Optional, Dict, Any
from app.config import settings

class GitLabService:
    """Service for interacting with the GitLab API."""

    def __init__(self, token: Optional[str] = None, url: Optional[str] = None):
        self.token = token or settings.gitlab_personal_access_token
        self.url = url or settings.gitlab_url
        self.gl = gitlab.Gitlab(self.url, private_token=self.token)

    def get_project(self, project_id: str):
        """Get a GitLab project by ID."""
        return self.gl.projects.get(project_id)

    def list_issues(self, project_id: str, **kwargs):
        """List issues for a project."""
        project = self.get_project(project_id)
        return project.issues.list(**kwargs)

    def create_issue(
        self,
        project_id: str,
        title: str,
        description: str,
        labels: List[str] = None,
        weight: int = None,
        due_date: str = None,
        milestone_id: int = None,
    ):
        """Create a new issue with full metadata."""
        project = self.get_project(project_id)
        issue_data = {
            "title": title,
            "description": description,
            "labels": labels or [],
        }
        if weight is not None:
            issue_data["weight"] = weight
        if due_date:
            issue_data["due_date"] = due_date
        if milestone_id:
            issue_data["milestone_id"] = milestone_id

        return project.issues.create(issue_data)

    def update_issue(
        self,
        project_id: str,
        issue_iid: int,
        **kwargs
    ):
        """Update an existing issue."""
        project = self.get_project(project_id)
        issue = project.issues.get(issue_iid)
        for key, value in kwargs.items():
            setattr(issue, key, value)
        issue.save()
        return issue

    def list_milestones(self, project_id: str):
        """List milestones for a project."""
        project = self.get_project(project_id)
        return project.milestones.list()

    def create_milestone(self, project_id: str, title: str, description: str = None, start_date: str = None, due_date: str = None):
        """Create a milestone."""
        project = self.get_project(project_id)
        return project.milestones.create({
            "title": title,
            "description": description,
            "start_date": start_date,
            "due_date": due_date
        })

    def list_labels(self, project_id: str):
        """List labels for a project."""
        project = self.get_project(project_id)
        return project.labels.list()

    def create_label(self, project_id: str, name: str, color: str, description: str = None):
        """Create a label."""
        project = self.get_project(project_id)
        return project.labels.create({
            "name": name,
            "color": color,
            "description": description
        })

gitlab_service = GitLabService()
