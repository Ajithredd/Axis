"""Script to safely prune all data from PostgreSQL and Qdrant while preserving the test user and their PAT."""

import asyncio
import logging
import uuid
from sqlalchemy import select, delete
from app.database import async_session
from app.models.user import User
from app.models.project import Project, ProjectConnector, SyncStatus
from app.models.event import Event
from app.models.embedding import Embedding
from app.models.feature import Feature, FeatureLink
from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge
from app.database.qdrant import get_qdrant_client, init_qdrant_collections
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CANONICAL_USER_ID = uuid.UUID("5dc41bda-2383-4e56-8f37-661cf313163d")

async def prune_project_dependencies(db, project_id: uuid.UUID):
    """Prunes all cascading dependency data for a project ID."""
    logger.info(f"Pruning data for project {project_id}...")
    await db.execute(delete(Embedding).where(Embedding.project_id == project_id))
    feature_ids_subquery = select(Feature.id).where(Feature.project_id == project_id)
    await db.execute(delete(FeatureLink).where(FeatureLink.feature_id.in_(feature_ids_subquery)))
    await db.execute(delete(Feature).where(Feature.project_id == project_id))
    await db.execute(delete(GraphEdge).where(GraphEdge.project_id == project_id))
    await db.execute(delete(Requirement).where(Requirement.project_id == project_id))
    await db.execute(delete(Decision).where(Decision.project_id == project_id))
    await db.execute(delete(Stakeholder).where(Stakeholder.project_id == project_id))
    await db.execute(delete(Event).where(Event.project_id == project_id))
    await db.execute(delete(ProjectConnector).where(ProjectConnector.project_id == project_id))

async def main():
    logger.info("Starting safe database cleanup and redesign preparation...")

    # 1. Clean Qdrant collections
    q_client = get_qdrant_client()
    collections_to_wipe = ["requirements", "decisions", "events"]
    for c_name in collections_to_wipe:
        try:
            logger.info(f"Deleting Qdrant collection: {c_name}")
            await q_client.delete_collection(collection_name=c_name)
        except Exception as e:
            logger.warning(f"Could not delete collection {c_name} (might not exist): {e}")

    # Recreate them fresh
    logger.info("Initializing clean Qdrant collections...")
    await init_qdrant_collections()

    # 2. Clean Postgres
    async with async_session() as db:
        # Check canonical user
        res = await db.execute(select(User).where(User.id == CANONICAL_USER_ID))
        user = res.scalar_one_or_none()
        if not user:
            logger.error(f"Canonical user {CANONICAL_USER_ID} not found in DB! Creating one.")
            user = User(
                id=CANONICAL_USER_ID,
                email="user@axis.ai",
                display_name="Axis Test User",
                gitlab_access_token=settings.gitlab_personal_access_token
            )
            db.add(user)
            await db.flush()
        else:
            logger.info(f"Preserving User: {user.display_name} (ID: {user.id})")
            if settings.gitlab_personal_access_token:
                logger.info("Updating user GitLab access token to current environment PAT.")
                user.gitlab_access_token = settings.gitlab_personal_access_token
                await db.flush()

        # Find all projects in DB
        res_projects = await db.execute(select(Project))
        all_projects = res_projects.scalars().all()
        
        # We will keep exactly one Project and its Connector if available, delete the rest.
        project_to_keep = None
        
        # Try to find one owned by CANONICAL_USER_ID with a valid GitLab connector
        for p in all_projects:
            if p.owner_id == CANONICAL_USER_ID:
                res_conn = await db.execute(
                    select(ProjectConnector).where(
                        ProjectConnector.project_id == p.id,
                        ProjectConnector.connector_type == "gitlab"
                    )
                )
                conn = res_conn.scalar_one_or_none()
                if conn and conn.access_token:
                    project_to_keep = p
                    logger.info(f"Selecting Project '{p.name}' (ID: {p.id}) to preserve (owned by canonical user and has GitLab connector).")
                    break

        # Fallback to any project owned by canonical user
        if not project_to_keep:
            for p in all_projects:
                if p.owner_id == CANONICAL_USER_ID:
                    project_to_keep = p
                    logger.info(f"Selecting Project '{p.name}' (ID: {p.id}) to preserve.")
                    break

        if not project_to_keep:
            # Create a default project
            project_to_keep = Project(
                id=uuid.uuid4(),
                name="Axis",
                description="Preserved Axis Integration Project",
                owner_id=CANONICAL_USER_ID
            )
            db.add(project_to_keep)
            await db.flush()
            logger.info(f"Created a clean default Project '{project_to_keep.name}' (ID: {project_to_keep.id})")

        # Let's ensure a GitLab connector exists for the project_to_keep
        res_conn = await db.execute(
            select(ProjectConnector).where(
                ProjectConnector.project_id == project_to_keep.id,
                ProjectConnector.connector_type == "gitlab"
            )
        )
        connector_to_keep = res_conn.scalar_one_or_none()
        if not connector_to_keep:
            connector_to_keep = ProjectConnector(
                project_id=project_to_keep.id,
                connector_type="gitlab",
                config={"gitlab_project_id": 82250147, "gitlab_url": settings.gitlab_url},
                access_token=user.gitlab_access_token or settings.gitlab_personal_access_token,
                sync_status=SyncStatus.PENDING
            )
            db.add(connector_to_keep)
            await db.flush()
            logger.info(f"Created/attached ProjectConnector for Project ID {project_to_keep.id}")
        else:
            logger.info(f"Preserving ProjectConnector ID: {connector_to_keep.id} (Project: {project_to_keep.id})")
            connector_to_keep.access_token = user.gitlab_access_token or settings.gitlab_personal_access_token
            connector_to_keep.sync_status = SyncStatus.PENDING
            connector_to_keep.last_synced_at = None
            connector_to_keep.sync_error = None
            await db.flush()

        # Delete all other projects
        for other_p in all_projects:
            if other_p.id != project_to_keep.id:
                logger.info(f"Pruning project {other_p.name} (ID: {other_p.id}) and all cascading dependencies.")
                await prune_project_dependencies(db, other_p.id)
                await db.execute(delete(Project).where(Project.id == other_p.id))

        # Manually clean ALL dependency data for the preserved canonical project itself
        await prune_project_dependencies(db, project_to_keep.id)

        # Delete all other users
        await db.execute(delete(User).where(User.id != CANONICAL_USER_ID))

        await db.commit()
        logger.info("Cleanup completed successfully. Only User and one clean empty Project (with PAT) remain.")

if __name__ == "__main__":
    asyncio.run(main())
