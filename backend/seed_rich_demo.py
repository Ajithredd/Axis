import asyncio
import uuid
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.project import Project
from app.models.feature import Feature
from app.models.graph import Requirement, Decision, Stakeholder, GraphEdge
from app.models.event import Event
from app.services.vector_sync import sync_node_to_vector_store

async def seed_rich_data():
    async with async_session() as db:
        # 1. Get or create test user
        uid = uuid.UUID('5dc41bda-2383-4e56-8f37-661cf313163d')
        user = await db.scalar(select(User).where(User.id == uid))
        if not user:
            user = User(id=uid, email='test@example.com', display_name='Test User')
            db.add(user)
            await db.flush()

        # 2. Check and clean existing demo project if any
        res = await db.execute(select(Project).where(Project.name == 'E-Commerce Platform Redesign'))
        proj = res.scalar_one_or_none()
        if proj:
            print("Project 'E-Commerce Platform Redesign' already exists. Deleting related data...")
            # Cascade manual deletes since relationships don't have cascade="all, delete" for events/features etc.
            from sqlalchemy import delete
            await db.execute(delete(GraphEdge).where(GraphEdge.project_id == proj.id))
            await db.execute(delete(Event).where(Event.project_id == proj.id))
            await db.execute(delete(Requirement).where(Requirement.project_id == proj.id))
            await db.execute(delete(Decision).where(Decision.project_id == proj.id))
            await db.execute(delete(Stakeholder).where(Stakeholder.project_id == proj.id))
            await db.execute(delete(Feature).where(Feature.project_id == proj.id))
            await db.delete(proj)
            await db.flush()

        proj = Project(
            name='E-Commerce Platform Redesign',
            description='Upgrade and secure the transaction core and authentication layout.',
            owner_id=user.id
        )
        db.add(proj)
        await db.flush()

        project_id = proj.id

        # 3. Create Stakeholders
        security_lead = Stakeholder(
            project_id=project_id,
            display_name="Sarah Jenkins",
            role="architect",
            email="sarah.jenkins@axisdev.io"
        )
        pm = Stakeholder(
            project_id=project_id,
            display_name="Marcus Vance",
            role="product_owner",
            email="marcus.vance@axisdev.io"
        )
        db.add_all([security_lead, pm])
        await db.flush()

        # 4. Create Features
        sso_feat = Feature(
            project_id=project_id,
            name="OAuth2 Enterprise Single Sign-On",
            description="Allows corporate accounts to authenticate using SSO providers like Okta or Azure AD."
        )
        payment_feat = Feature(
            project_id=project_id,
            name="Stripe Billing Integration",
            description="Integrate Stripe APIs to handle secure recurring subscriptions, checkout sessions, and webhooks."
        )
        db.add_all([sso_feat, payment_feat])
        await db.flush()

        # 5. Create Requirements
        req_mfa = Requirement(
            project_id=project_id,
            title="MFA Enforcement Policy",
            description="All administrative or privileged users must authenticate using Multi-Factor Authentication.",
            requirement_type="non_functional",
            status="approved"
        )
        req_token = Requirement(
            project_id=project_id,
            title="JWT Token Rotation",
            description="Token rotation mechanisms must invalidate refresh tokens every 24 hours to mitigate session hijacking.",
            requirement_type="functional",
            status="approved"
        )
        req_pci = Requirement(
            project_id=project_id,
            title="PCI-DSS Compliance Level 2",
            description="Payment credentials must never be persisted in plaintext. Use Stripe Elements for tokenization on frontend.",
            requirement_type="constraint",
            status="approved"
        )
        db.add_all([req_mfa, req_token, req_pci])
        await db.flush()

        # 6. Create Decisions
        dec_auth = Decision(
            project_id=project_id,
            title="Adopt Okta Integration for Corporate SSO",
            rationale="We decided to use Okta as our principal authentication provider because of its native support for OIDC and custom attribute mapping.",
            status="accepted"
        )
        dec_stripe = Decision(
            project_id=project_id,
            title="Utilize Stripe Hosted Checkout",
            rationale="We opted to use Stripe Hosted Checkout pages rather than custom forms to reduce our PCI-DSS compliance surface.",
            status="accepted"
        )
        db.add_all([dec_auth, dec_stripe])
        await db.flush()

        # 7. Create Events (to test child-parent chunking & telemetry)
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        event1 = Event(
            project_id=project_id,
            connector_type="manual_seed",
            source_id="seed_evt_1",
            source_timestamp=now,
            event_type="security_audit",
            title="Security Audit on Auth Logs",
            content="A complete security audit was conducted on Auth Logs. The audit found that JWT tokens lacked rotation policies, exposing the platform to session hijacking risks. We recommended enforcing refresh token rotations every 24 hours. The security team also flagged the necessity of enforcing MFA for all administrator logins.",
            metadata={"auditor": "Sarah Jenkins", "target": "Authentication Modules"}
        )
        event2 = Event(
            project_id=project_id,
            connector_type="manual_seed",
            source_id="seed_evt_2",
            source_timestamp=now,
            event_type="architecture_review",
            title="Stripe Payment Core Setup Review",
            content="During the architecture review of Stripe core configurations, Marcus and Sarah agreed to mandate Stripe Hosted Checkout. This will outsource credit card detail handling entirely to Stripe's servers, maintaining our compliance scope within PCI-DSS SAQ-A limits.",
            metadata={"reviewer": "Marcus Vance", "target": "Billing Core"}
        )
        db.add_all([event1, event2])
        await db.flush()

        # 8. Create Graph Edges (Connections)
        edges = [
            # Feature -> Requirement
            GraphEdge(project_id=project_id, source_id=sso_feat.id, target_id=req_mfa.id, source_type='features', target_type='requirements', edge_type='requires', weight=1.0),
            GraphEdge(project_id=project_id, source_id=sso_feat.id, target_id=req_token.id, source_type='features', target_type='requirements', edge_type='requires', weight=1.0),
            GraphEdge(project_id=project_id, source_id=payment_feat.id, target_id=req_pci.id, source_type='features', target_type='requirements', edge_type='requires', weight=1.0),
            # Feature -> Decision (using decided_by)
            GraphEdge(project_id=project_id, source_id=sso_feat.id, target_id=dec_auth.id, source_type='features', target_type='decisions', edge_type='decided_by', weight=1.0),
            GraphEdge(project_id=project_id, source_id=payment_feat.id, target_id=dec_stripe.id, source_type='features', target_type='decisions', edge_type='decided_by', weight=1.0),
            # Stakeholder -> Feature (using authored/reviewed)
            GraphEdge(project_id=project_id, source_id=security_lead.id, target_id=sso_feat.id, source_type='stakeholders', target_type='features', edge_type='reviewed', weight=1.0),
            GraphEdge(project_id=project_id, source_id=pm.id, target_id=payment_feat.id, source_type='stakeholders', target_type='features', edge_type='authored', weight=1.0)
        ]
        db.add_all(edges)
        await db.commit()

        print(f"Database objects successfully seeded for Project ID: {project_id}")

        # 9. Sync to Vector Database (Qdrant)
        sync_items = [
            ('features', sso_feat.id, 'Feature', f"{sso_feat.name}: {sso_feat.description}"),
            ('features', payment_feat.id, 'Feature', f"{payment_feat.name}: {payment_feat.description}"),
            ('requirements', req_mfa.id, 'Requirement', f"{req_mfa.title}: {req_mfa.description}"),
            ('requirements', req_token.id, 'Requirement', f"{req_token.title}: {req_token.description}"),
            ('requirements', req_pci.id, 'Requirement', f"{req_pci.title}: {req_pci.description}"),
            ('decisions', dec_auth.id, 'Decision', f"{dec_auth.title}: {dec_auth.rationale}"),
            ('decisions', dec_stripe.id, 'Decision', f"{dec_stripe.title}: {dec_stripe.rationale}"),
            ('stakeholders', security_lead.id, 'Stakeholder', f"{security_lead.display_name}: {security_lead.role} - {security_lead.email}"),
            ('stakeholders', pm.id, 'Stakeholder', f"{pm.display_name}: {pm.role} - {pm.email}")
        ]

        # For Events, chunk them using settings config (Parent-Child chunking)
        from app.config import settings
        from app.services.embedding import chunk_text
        
        for event in [event1, event2]:
            chunks = chunk_text(event.content, chunk_size=settings.child_chunk_size, chunk_overlap=settings.child_chunk_overlap)
            print(f"Event '{event.title}' chunked into {len(chunks)} fragments.")
            for i, chunk in enumerate(chunks):
                # Unique ID for each chunk
                chunk_uuid = uuid.uuid5(event.id, f"chunk_{i}")
                await sync_node_to_vector_store(
                    collection_name='events',
                    node_id=chunk_uuid,
                    project_id=project_id,
                    node_type='EventChunk',
                    content=chunk,
                    metadata={"parent_event_id": str(event.id), "event_title": event.title}
                )

        for coll, node_id, node_type, text in sync_items:
            await sync_node_to_vector_store(
                collection_name=coll,
                node_id=node_id,
                project_id=project_id,
                node_type=node_type,
                content=text
            )

        print("Qdrant Collections Synced Successfully!")
        print(f"\n--- USE THIS PROJECT ID TO QUERY THE RAG ---")
        print(project_id)

if __name__ == '__main__':
    asyncio.run(seed_rich_data())
