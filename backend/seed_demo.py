import asyncio
import uuid
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.project import Project
from app.models.feature import Feature
from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge

async def seed_data():
    async with async_session() as db:
        # Get or create user
        uid = uuid.UUID('5dc41bda-2383-4e56-8f37-661cf313163d')
        user = await db.scalar(select(User).where(User.id == uid))
        if not user:
            user = User(id=uid, email='test@example.com', display_name='Test User')
            db.add(user)
            await db.flush()

        # Check if project exists
        res = await db.execute(select(Project).where(Project.name == 'Axis Demo Project'))
        proj = res.scalar_one_or_none()
        
        if proj:
            print("Project already exists. Please run clean_db.py first if you want to recreate.")
            return
            
        proj = Project(
            name='Axis Demo Project',
            description='A demo project to showcase the Axis RAG engine.',
            owner_id=user.id
        )
        db.add(proj)
        await db.flush()
        
        # Create a feature
        feat = Feature(
            project_id=proj.id,
            name="SSO Login Configuration",
            description="This feature allows users to log in securely using Single Sign-On (SSO) via Okta or Google Auth."
        )
        db.add(feat)
        
        # Create a requirement
        req = Requirement(
            project_id=proj.id,
            title="Secure SSO Workflow",
            description="We must support secure SSO login workflow to comply with enterprise security standards.",
            requirement_type="non_functional",
            status="approved"
        )
        db.add(req)
        
        # Create a stakeholder
        stake = Stakeholder(
            project_id=proj.id,
            display_name="Security Team",
            role="architect",
            email="security@example.com"
        )
        db.add(stake)
        
        await db.flush()
        
        # Create an edge
        edge = GraphEdge(
            project_id=proj.id,
            source_id=feat.id,
            target_id=req.id,
            source_type='features',
            target_type='requirements',
            edge_type='requires',
            weight=1.0
        )
        db.add(edge)
        
        await db.commit()
        print("Successfully added demo data (Project, Feature, Requirement, Stakeholder)!")
        
        # Now trigger Qdrant sync for these items
        from app.services.vector_sync import sync_node_to_vector_store
        await sync_node_to_vector_store(
            collection_name='features', 
            node_id=feat.id, 
            project_id=proj.id, 
            node_type='Feature', 
            content=f"{feat.name}: {feat.description}"
        )
        await sync_node_to_vector_store(
            collection_name='requirements', 
            node_id=req.id, 
            project_id=proj.id, 
            node_type='Requirement', 
            content=f"{req.title}: {req.description}"
        )
        await sync_node_to_vector_store(
            collection_name='stakeholders', 
            node_id=stake.id, 
            project_id=proj.id, 
            node_type='Stakeholder', 
            content=f"{stake.display_name}: {stake.role} - {stake.email}"
        )
        print("Successfully synced data to Qdrant!")

if __name__ == '__main__':
    asyncio.run(seed_data())
