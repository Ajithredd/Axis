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

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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


class ImportGitlabProjectRequest(BaseModel):
    gitlab_project_id: str
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


@router.get("/gitlab/available")
async def list_available_gitlab_projects(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List GitLab projects available to the user."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.gitlab_access_token:
        raise HTTPException(400, "User not found or missing GitLab access token")

    # Fetch user's existing projects and their connectors
    project_connectors_res = await db.execute(
        select(ProjectConnector)
        .join(Project)
        .where(Project.owner_id == uuid.UUID(user_id), ProjectConnector.connector_type == "gitlab")
    )
    existing_connectors = project_connectors_res.scalars().all()
    connected_project_ids = set()
    for pc in existing_connectors:
        if pc.config and "gitlab_project_id" in pc.config:
            connected_project_ids.add(str(pc.config["gitlab_project_id"]))

    # Use the token to fetch projects
    import gitlab
    from app.services.gitlab import GitLabService
    gl_service = GitLabService(token=user.gitlab_access_token)
    try:
        gl_projects = gl_service.list_user_projects()
        return {
            "projects": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "name_with_namespace": p.name_with_namespace,
                    "description": p.description,
                    "avatar_url": p.avatar_url,
                    "web_url": p.web_url,
                    "is_connected": str(p.id) in connected_project_ids,
                }
                for p in gl_projects
            ]
        }
    except gitlab.exceptions.GitlabError as e:
        response_code = getattr(e, 'response_code', None)
        if response_code in (401, 403):
            raise HTTPException(response_code, f"GitLab authorization failed: {getattr(e, 'error_message', str(e))}")
        raise HTTPException(500, f"Failed to fetch GitLab projects: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch GitLab projects: {str(e)}")


@router.post("/gitlab/import")
async def import_gitlab_project(
    req: ImportGitlabProjectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Import a GitLab project and start sync."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(req.user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.gitlab_access_token:
        raise HTTPException(400, "User not found or missing GitLab access token")

    # Check if this GitLab project is already connected
    project_connectors_res = await db.execute(
        select(ProjectConnector)
        .join(Project)
        .where(Project.owner_id == uuid.UUID(req.user_id), ProjectConnector.connector_type == "gitlab")
    )
    existing_connectors = project_connectors_res.scalars().all()
    for pc in existing_connectors:
        if pc.config and pc.config.get("gitlab_project_id") == int(req.gitlab_project_id):
            raise HTTPException(400, "This GitLab project is already connected")

    import gitlab
    from app.services.gitlab import GitLabService
    gl_service = GitLabService(token=user.gitlab_access_token)
    try:
        gl_project = gl_service.get_project(req.gitlab_project_id)
    except gitlab.exceptions.GitlabError as e:
        response_code = getattr(e, 'response_code', None)
        if response_code in (401, 403):
            raise HTTPException(response_code, f"GitLab authorization failed: {getattr(e, 'error_message', str(e))}")
        raise HTTPException(404, f"GitLab project not found: {str(e)}")
    except Exception as e:
        raise HTTPException(404, f"GitLab project not found: {str(e)}")

    # 1. Create internal project
    project = Project(
        name=gl_project.name,
        description=gl_project.description,
        owner_id=uuid.UUID(req.user_id),
    )
    db.add(project)
    await db.flush()

    # 2. Connect source
    connector = connector_registry.get("gitlab")
    if not connector:
        raise HTTPException(500, "GitLab connector not registered")

    webhook_secret = secrets.token_urlsafe(32)
    config = {
        "gitlab_project_id": int(gl_project.id),
        "gitlab_url": settings.gitlab_url,
    }
    
    project_connector = ProjectConnector(
        project_id=project.id,
        connector_type="gitlab",
        config=config,
        access_token=user.gitlab_access_token,
        webhook_secret=webhook_secret,
        sync_status=SyncStatus.PENDING,
    )
    db.add(project_connector)
    await db.commit() # commit so background task sees the connector

    try:
        webhook_url = f"{settings.api_url}/api/webhooks/gitlab/{project.id}"
        await connector.setup_webhook(
            config=config,
            access_token=user.gitlab_access_token,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
    except Exception as e:
        print(f"Warning: Failed to setup webhook: {e}")

    # 3. Trigger initial sync
    # We can't pass the request `db` session to a background task because it closes.
    # But `ingest_project` expects an AsyncSession.
    # So we will wrap it in a local async session.
    from app.database import async_session
    async def run_sync(pc_id):
        async with async_session() as session:
            res = await session.execute(select(ProjectConnector).where(ProjectConnector.id == pc_id))
            pc = res.scalar_one_or_none()
            if pc:
                await ingest_project(session, pc)
    
    background_tasks.add_task(run_sync, project_connector.id)

    return {
        "id": str(project.id),
        "name": project.name,
        "connector_id": str(project_connector.id),
        "status": "importing",
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


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a project and all associated data."""
    from sqlalchemy import delete
    from app.models.project import Project, ProjectConnector
    from app.models.event import Event
    from app.models.embedding import Embedding
    from app.models.feature import Feature, FeatureLink
    from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge
    
    proj_uuid = uuid.UUID(project_id)
    
    res = await db.execute(select(Project).where(Project.id == proj_uuid))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
        
    try:
        # Delete embeddings
        await db.execute(delete(Embedding).where(Embedding.project_id == proj_uuid))
        
        # Delete feature links
        feature_ids_subquery = select(Feature.id).where(Feature.project_id == proj_uuid)
        await db.execute(delete(FeatureLink).where(FeatureLink.feature_id.in_(feature_ids_subquery)))
        
        # Delete features
        await db.execute(delete(Feature).where(Feature.project_id == proj_uuid))
        
        # Delete graph edges, requirements, decisions, stakeholders
        await db.execute(delete(GraphEdge).where(GraphEdge.project_id == proj_uuid))
        await db.execute(delete(Requirement).where(Requirement.project_id == proj_uuid))
        await db.execute(delete(Decision).where(Decision.project_id == proj_uuid))
        await db.execute(delete(Stakeholder).where(Stakeholder.project_id == proj_uuid))
        
        # Delete events
        await db.execute(delete(Event).where(Event.project_id == proj_uuid))
        
        # Delete connectors
        await db.execute(delete(ProjectConnector).where(ProjectConnector.project_id == proj_uuid))
        
        # Delete project itself
        await db.execute(delete(Project).where(Project.id == proj_uuid))
        
        await db.commit()
        return {"status": "success", "message": f"Project '{project.name}' deleted successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Failed to delete project: {str(e)}")
