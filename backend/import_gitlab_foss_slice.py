import asyncio
import uuid
from sqlalchemy import select, delete
from app.database import async_session
from app.models.user import User
from app.models.project import Project, ProjectConnector, SyncStatus
from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge
from app.models.event import Event
from app.connectors.gitlab.client import GitLabClient
from app.connectors.gitlab.connector import GitLabConnector
from app.connectors.registry import connector_registry
from app.services.ingestion import ingest_project
from app.config import settings

# 1. Monkeypatch GitLabClient to fetch a limited slice of data
original_paginate = GitLabClient._paginate

async def patched_paginate(self, endpoint: str, params: dict | None = None) -> list[dict]:
    params = params or {}
    
    # Customize limits to make testing quick but rich
    if "issues" in endpoint and "notes" not in endpoint:
        params["per_page"] = 30  # Fetch 30 issues
    elif "merge_requests" in endpoint and "notes" not in endpoint:
        params["per_page"] = 20  # Fetch 20 merge requests
    elif "commits" in endpoint:
        params["per_page"] = 30  # Fetch 30 commits
    elif "notes" in endpoint:
        params["per_page"] = 10  # Max 10 comments per issue/MR to avoid overload
    else:
        params["per_page"] = 10  # Other lists (e.g. milestones)
        
    print(f"Fetching page 1 of {endpoint} with params={params}...")
    
    # Force single-page pagination by fetching only page 1
    params["page"] = 1
    resp = await self._client.get(f"{self.api_url}{endpoint}", params=params)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]

GitLabClient._paginate = patched_paginate

async def import_foss_slice():
    connector_registry.discover()
    async with async_session() as db:
        # 2. Get or create test user and ensure they have the token
        uid = uuid.UUID('5dc41bda-2383-4e56-8f37-661cf313163d')
        user = await db.scalar(select(User).where(User.id == uid))
        
        token = settings.gitlab_personal_access_token
        if not token:
            print("WARNING: GITLAB_PERSONAL_ACCESS_TOKEN is not configured in .env.")
            print("Attempting to connect without authentication (for public projects)...")
            token = "dummy-token-public-read"
            
        if not user:
            user = User(
                id=uid,
                email='test@example.com',
                display_name='Test User',
                gitlab_access_token=token
            )
            db.add(user)
            await db.flush()
        else:
            user.gitlab_access_token = token
            db.add(user)
            await db.flush()

        # 3. Clean up existing FOSS project
        project_name = 'GitLab CE (FOSS) Slice'
        res = await db.execute(select(Project).where(Project.name == project_name))
        proj = res.scalar_one_or_none()
        if proj:
            print(f"Project '{project_name}' already exists. Deleting related data...")
            await db.execute(delete(GraphEdge).where(GraphEdge.project_id == proj.id))
            await db.execute(delete(Event).where(Event.project_id == proj.id))
            await db.execute(delete(Requirement).where(Requirement.project_id == proj.id))
            await db.execute(delete(Decision).where(Decision.project_id == proj.id))
            await db.execute(delete(Stakeholder).where(Stakeholder.project_id == proj.id))
            
            # Delete any features and connectors
            from app.models.feature import Feature, FeatureLink
            await db.execute(delete(FeatureLink).where(FeatureLink.feature_id.in_(
                select(Feature.id).where(Feature.project_id == proj.id)
            )))
            await db.execute(delete(Feature).where(Feature.project_id == proj.id))
            await db.execute(delete(ProjectConnector).where(ProjectConnector.project_id == proj.id))
            await db.delete(proj)
            await db.commit()
            print("Old project data cleaned up successfully.")

        # 4. Create new FOSS project
        proj = Project(
            name=project_name,
            description='A curated slice of the official GitLab Community Edition (FOSS) codebase and issues for testing Axis.',
            owner_id=user.id
        )
        db.add(proj)
        await db.flush()

        # 5. Connect GitLab connector for gitlab-org/gitlab-foss (ID: 13083)
        config = {
            "gitlab_project_id": 13083,
            "gitlab_url": "https://gitlab.com"
        }
        pc = ProjectConnector(
            project_id=proj.id,
            connector_type="gitlab",
            config=config,
            access_token=token,
            webhook_secret="mock-secret",
            sync_status=SyncStatus.PENDING
        )
        db.add(pc)
        await db.commit()
        
        print(f"Successfully created project '{project_name}' and connected gitlab-org/gitlab-foss.")
        print("Starting ingestion. This may take a few minutes as we fetch issues, MRs, commits, comments, generate embeddings and build the Intelligence Graph...")
        
        # Reload pc in session to run sync
        async with async_session() as run_db:
            res = await run_db.execute(select(ProjectConnector).where(ProjectConnector.id == pc.id))
            pc_loaded = res.scalar_one()
            stats = await ingest_project(run_db, pc_loaded)
            
            # Mark connector as completed
            pc_loaded.sync_status = SyncStatus.COMPLETED
            await run_db.commit()
            
            print("\nIngestion completed successfully!")
            print(f"Stats: {stats}")
            print(f"--- USE THIS PROJECT ID TO QUERY THE RAG ---")
            print(proj.id)

if __name__ == '__main__':
    asyncio.run(import_foss_slice())
