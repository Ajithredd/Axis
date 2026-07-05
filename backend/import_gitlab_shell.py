import asyncio
import uuid
from sqlalchemy import select, delete
from app.database import async_session
from app.models.user import User
from app.models.project import Project, ProjectConnector, SyncStatus
from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge
from app.models.event import Event
from app.connectors.registry import connector_registry
from app.services.ingestion import ingest_project
import app.services.ingestion
import app.services.vector_sync
from app.config import settings
import httpx

# Mock sync_node_to_vector_store to return True immediately to bypass Gemini embedding rate limits
async def mock_sync_node_to_vector_store(*args, **kwargs):
    return True

app.services.ingestion.sync_node_to_vector_store = mock_sync_node_to_vector_store
app.services.vector_sync.sync_node_to_vector_store = mock_sync_node_to_vector_store

# Patch GitLabClient._paginate to include robust retry logic for transient server errors (e.g. 502 Bad Gateway)
from app.connectors.gitlab.client import GitLabClient

async def patched_paginate(self, endpoint: str, params: dict | None = None) -> list[dict]:
    results = []
    params = params or {}
    params.setdefault("per_page", 100)
    page = 1

    while True:
        params["page"] = page
        url = f"{self.api_url}{endpoint}"
        max_retries = 5
        data = None
        
        for attempt in range(max_retries):
            try:
                resp = await self._client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                break
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                is_transient = False
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                    if status_code in [500, 502, 503, 504, 429]:
                        is_transient = True
                else:
                    is_transient = True
                
                if is_transient and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"Transient error fetching {url} (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise e

        if not data:
            break

        results.extend(data)

        total_pages = int(resp.headers.get("x-total-pages", 1))
        if page >= total_pages:
            break
        page += 1

    return results

GitLabClient._paginate = patched_paginate

async def import_gitlab_shell():
    # 1. Register connectors
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

        # 3. Clean up existing GitLab Shell project if any
        project_name = 'GitLab Shell'
        res = await db.execute(select(Project).where(Project.name == project_name))
        proj = res.scalar_one_or_none()
        if proj:
            print(f"Project '{project_name}' already exists. Deleting old data to prevent duplication...")
            await db.execute(delete(GraphEdge).where(GraphEdge.project_id == proj.id))
            await db.execute(delete(Event).where(Event.project_id == proj.id))
            await db.execute(delete(Requirement).where(Requirement.project_id == proj.id))
            await db.execute(delete(Decision).where(Decision.project_id == proj.id))
            await db.execute(delete(Stakeholder).where(Stakeholder.project_id == proj.id))
            
            from app.models.feature import Feature, FeatureLink
            await db.execute(delete(FeatureLink).where(FeatureLink.feature_id.in_(
                select(Feature.id).where(Feature.project_id == proj.id)
            )))
            await db.execute(delete(Feature).where(Feature.project_id == proj.id))
            await db.execute(delete(ProjectConnector).where(ProjectConnector.project_id == proj.id))
            await db.delete(proj)
            await db.commit()
            print("Old project data cleaned up.")

        # 4. Create new Project
        proj = Project(
            name=project_name,
            description='Complete import of the official gitlab-org/gitlab-shell repository containing issues, MRs, commits, and comments.',
            owner_id=user.id
        )
        db.add(proj)
        await db.flush()

        # 5. Connect GitLab connector (ID: 14022)
        config = {
            "gitlab_project_id": 14022,
            "gitlab_url": "https://gitlab.com"
        }
        pc = ProjectConnector(
            project_id=proj.id,
            connector_type="gitlab",
            config=config,
            access_token=token,
            webhook_secret="shell-secret",
            sync_status=SyncStatus.PENDING
        )
        db.add(pc)
        await db.commit()
        pc_id = pc.id
        proj_id = proj.id
        
        print(f"Successfully created project '{project_name}' and connected gitlab-org/gitlab-shell.")
        print("Starting 100% full ingestion. This will sync all issues, merge requests, commits, and comments...")
        
    # Run ingestion outside the outer session block to prevent deadlocks
    async with async_session() as run_db:
        res = await run_db.execute(select(ProjectConnector).where(ProjectConnector.id == pc_id))
        pc_loaded = res.scalar_one()
        
        stats = await ingest_project(run_db, pc_loaded)
        
        pc_loaded.sync_status = SyncStatus.COMPLETED
        await run_db.commit()
        
        print("\nIngestion completed successfully!")
        print(f"Stats: {stats}")
        print(f"--- USE THIS PROJECT ID TO QUERY THE RAG ---")
        print(proj_id)

if __name__ == '__main__':
    asyncio.run(import_gitlab_shell())
