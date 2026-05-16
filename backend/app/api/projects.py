"""
Project routes — connect sources, trigger syncs, manage projects.

Key endpoints:
  POST /api/projects/                 → create a project
  POST /api/projects/{id}/connect     → connect a source (GitLab, Slack, etc.)
  POST /api/projects/{id}/sync        → trigger full sync
  GET  /api/projects/{id}/status      → sync status
  GET  /api/projects/                 → list user's projects
"""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.project import Project, ProjectConnector, SyncStatus
from app.models.user import User
from app.connectors.registry import connector_registry
from app.services.ingestion import ingest_project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    user_id: str  # Simplified — use JWT auth in production


class ConnectSourceRequest(BaseModel):
    connector_type: str  # e.g., "gitlab", "slack", "confluence"
    config: dict  # Connector-specific config
    user_id: str


@router.post("/")
async def create_project(
    req: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new Axis project."""
    project = Project(
        name=req.name,
        description=req.description,
        owner_id=uuid.UUID(req.user_id),
    )
    db.add(project)
    await db.flush()

    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
    }


@router.post("/{project_id}/connect")
async def connect_source(
    project_id: str,
    req: ConnectSourceRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Connect an external source to a project.

    This is connector-agnostic — works for GitLab, Slack, Confluence, etc.
    The connector_type determines which plugin handles it.
    """
    connector = connector_registry.get(req.connector_type)
    if not connector:
        raise HTTPException(404, f"Connector '{req.connector_type}' not found")

    # Validate the config
    if not await connector.validate_config(req.config):
        raise HTTPException(400, f"Invalid config for '{req.connector_type}' connector")

    # Get user's access token for this connector
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(req.user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # Get the token based on connector type
    access_token = None
    if req.connector_type == "gitlab":
        access_token = user.gitlab_access_token
    # Future: elif req.connector_type == "slack": access_token = user.slack_access_token

    if not access_token:
        raise HTTPException(
            400, f"No {req.connector_type} token found. Please authenticate first."
        )

    # Create the connector link
    webhook_secret = secrets.token_urlsafe(32)
    project_connector = ProjectConnector(
        project_id=uuid.UUID(project_id),
        connector_type=req.connector_type,
        config=req.config,
        access_token=access_token,
        webhook_secret=webhook_secret,
        sync_status=SyncStatus.PENDING,
    )
    db.add(project_connector)
    await db.flush()

    # Set up webhook for real-time updates
    webhook_url = f"{settings.api_url}/api/webhooks/{req.connector_type}/{project_id}"
    webhook_ok = await connector.setup_webhook(
        config=req.config,
        access_token=access_token,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
    )

    return {
        "connector_id": str(project_connector.id),
        "connector_type": req.connector_type,
        "status": project_connector.sync_status.value,
        "webhook_registered": webhook_ok,
    }


@router.post("/{project_id}/sync")
async def trigger_sync(
    project_id: str,
    connector_type: str = "gitlab",
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full sync for a project's connector."""
    result = await db.execute(
        select(ProjectConnector).where(
            ProjectConnector.project_id == uuid.UUID(project_id),
            ProjectConnector.connector_type == connector_type,
        )
    )
    pc = result.scalar_one_or_none()
    if not pc:
        raise HTTPException(404, "Connector not found for this project")

    # Run sync (in production, dispatch to Celery)
    stats = await ingest_project(db, pc)

    return {
        "status": "completed",
        "stats": stats,
    }


@router.get("/{project_id}/status")
async def get_sync_status(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the sync status of all connectors for a project."""
    result = await db.execute(
        select(ProjectConnector).where(
            ProjectConnector.project_id == uuid.UUID(project_id)
        )
    )
    connectors = result.scalars().all()

    return {
        "connectors": [
            {
                "id": str(pc.id),
                "type": pc.connector_type,
                "status": pc.sync_status.value,
                "last_synced": pc.last_synced_at.isoformat() if pc.last_synced_at else None,
                "error": pc.sync_error,
            }
            for pc in connectors
        ]
    }


@router.get("/")
async def list_projects(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all projects for a user."""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.connectors))
        .where(Project.owner_id == uuid.UUID(user_id))
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    return {
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at.isoformat(),
                "connectors": [
                    {
                        "type": c.connector_type,
                        "status": c.sync_status.value,
                        "last_synced": c.last_synced_at.isoformat() if c.last_synced_at else None,
                    }
                    for c in p.connectors
                ],
            }
            for p in projects
        ]
    }
