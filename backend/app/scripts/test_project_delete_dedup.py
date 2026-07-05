import asyncio
import uuid
from sqlalchemy import select, func
from app.database import async_session
from app.models.user import User
from app.models.project import Project, ProjectConnector
from app.models.event import Event
from app.models.embedding import Embedding
from app.models.feature import Feature, FeatureLink
from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge
from app.api.projects import list_available_gitlab_projects, import_gitlab_project, ImportGitlabProjectRequest, delete_project
from fastapi import HTTPException
from fastapi.background import BackgroundTasks
from app.connectors.registry import connector_registry

user_id = "5dc41bda-2383-4e56-8f37-661cf313163d"

async def main():
    print("--- Testing GitLab Deduplication & Cascading Project Deletion ---")
    
    # 0. Discover connectors
    connector_registry.discover()
    
    # 1. Update user token to valid ENV token
    from app.config import settings
    valid_token = settings.gitlab_personal_access_token
    print(f"Using token: {valid_token[:15]}...")
    
    async with async_session() as db:
        res = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = res.scalar_one_or_none()
        original_token = user.gitlab_access_token
        user.gitlab_access_token = valid_token
        await db.commit()
        print("Updated user token in DB.")

    try:
        # 2. Get available projects and verify is_connected flag
        async with async_session() as db:
            avail_res = await list_available_gitlab_projects(user_id=user_id, db=db)
            projects = avail_res.get("projects", [])
            print(f"\nAvailable projects: {len(projects)}")
            for p in projects:
                print(f"  - {p['name']} (ID: {p['id']}) | is_connected: {p.get('is_connected')}")
            
            if not projects:
                print("No projects available to test.")
                return

            target_project = projects[0]
            
            # 3. Verify duplicate connection prevention (trying to import again)
            print(f"\nVerifying duplicate connection prevention for project {target_project['name']}...")
            bg_tasks = BackgroundTasks()
            req = ImportGitlabProjectRequest(
                user_id=user_id,
                gitlab_project_id=target_project['id']
            )
            
            try:
                await import_gitlab_project(req=req, background_tasks=bg_tasks, db=db)
                print("FAIL: Managed to double import a project!")
            except HTTPException as e:
                print(f"SUCCESS: Prevented double import with exception: HTTP {e.status_code} - {e.detail}")
                assert e.status_code == 400
                assert "already connected" in e.detail

        # 4. Count and delete a project to verify cascading deletion
        async with async_session() as db:
            # Let's find projects in DB
            res = await db.execute(select(Project).where(Project.owner_id == uuid.UUID(user_id)))
            db_projects = res.scalars().all()
            print(f"\nProjects in DB: {len(db_projects)}")
            for db_p in db_projects:
                print(f"  - {db_p.name} (ID: {db_p.id})")
                
            if not db_projects:
                print("No projects in DB to delete.")
                return
                
            project_to_delete = db_projects[0]
            proj_id = project_to_delete.id
            print(f"\nTargeting Project for Deletion: {project_to_delete.name} (ID: {proj_id})")
            
            # Count current related entities
            embedding_cnt = (await db.execute(select(func.count(Embedding.id)).where(Embedding.project_id == proj_id))).scalar()
            feature_cnt = (await db.execute(select(func.count(Feature.id)).where(Feature.project_id == proj_id))).scalar()
            req_cnt = (await db.execute(select(func.count(Requirement.id)).where(Requirement.project_id == proj_id))).scalar()
            dec_cnt = (await db.execute(select(func.count(Decision.id)).where(Decision.project_id == proj_id))).scalar()
            stake_cnt = (await db.execute(select(func.count(Stakeholder.id)).where(Stakeholder.project_id == proj_id))).scalar()
            edge_cnt = (await db.execute(select(func.count(GraphEdge.id)).where(GraphEdge.project_id == proj_id))).scalar()
            event_cnt = (await db.execute(select(func.count(Event.id)).where(Event.project_id == proj_id))).scalar()
            conn_cnt = (await db.execute(select(func.count(ProjectConnector.id)).where(ProjectConnector.project_id == proj_id))).scalar()
            
            print(f"Counts before deletion:")
            print(f"  - Embeddings: {embedding_cnt}")
            print(f"  - Features: {feature_cnt}")
            print(f"  - Requirements: {req_cnt}")
            print(f"  - Decisions: {dec_cnt}")
            print(f"  - Stakeholders: {stake_cnt}")
            print(f"  - GraphEdges: {edge_cnt}")
            print(f"  - Events: {event_cnt}")
            print(f"  - Connectors: {conn_cnt}")
            
            # 5. Call delete_project endpoint
            print(f"\nDeleting project {project_to_delete.name}...")
            del_res = await delete_project(project_id=str(proj_id), db=db)
            print(f"Deletion result: {del_res}")
            
        # 6. Verify they are all 0 now
        async with async_session() as db:
            embedding_cnt_after = (await db.execute(select(func.count(Embedding.id)).where(Embedding.project_id == proj_id))).scalar()
            feature_cnt_after = (await db.execute(select(func.count(Feature.id)).where(Feature.project_id == proj_id))).scalar()
            req_cnt_after = (await db.execute(select(func.count(Requirement.id)).where(Requirement.project_id == proj_id))).scalar()
            dec_cnt_after = (await db.execute(select(func.count(Decision.id)).where(Decision.project_id == proj_id))).scalar()
            stake_cnt_after = (await db.execute(select(func.count(Stakeholder.id)).where(Stakeholder.project_id == proj_id))).scalar()
            edge_cnt_after = (await db.execute(select(func.count(GraphEdge.id)).where(GraphEdge.project_id == proj_id))).scalar()
            event_cnt_after = (await db.execute(select(func.count(Event.id)).where(Event.project_id == proj_id))).scalar()
            conn_cnt_after = (await db.execute(select(func.count(ProjectConnector.id)).where(ProjectConnector.project_id == proj_id))).scalar()
            project_cnt_after = (await db.execute(select(func.count(Project.id)).where(Project.id == proj_id))).scalar()
            
            print(f"\nCounts after deletion:")
            print(f"  - Embeddings: {embedding_cnt_after}")
            print(f"  - Features: {feature_cnt_after}")
            print(f"  - Requirements: {req_cnt_after}")
            print(f"  - Decisions: {dec_cnt_after}")
            print(f"  - Stakeholders: {stake_cnt_after}")
            print(f"  - GraphEdges: {edge_cnt_after}")
            print(f"  - Events: {event_cnt_after}")
            print(f"  - Connectors: {conn_cnt_after}")
            print(f"  - Project itself: {project_cnt_after}")
            
            assert embedding_cnt_after == 0
            assert feature_cnt_after == 0
            assert req_cnt_after == 0
            assert dec_cnt_after == 0
            assert stake_cnt_after == 0
            assert edge_cnt_after == 0
            assert event_cnt_after == 0
            assert conn_cnt_after == 0
            assert project_cnt_after == 0
            print("\nSUCCESS: All cascade counts verified to be 0! The project was cleanly deleted.")

    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Restore original token
        async with async_session() as db:
            res = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user = res.scalar_one_or_none()
            user.gitlab_access_token = original_token
            await db.commit()
            print("Restored original token in DB.")

if __name__ == '__main__':
    asyncio.run(main())
