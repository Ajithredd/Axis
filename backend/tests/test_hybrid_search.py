import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session, init_db
from app.models.project import Project
from app.models.graph import Requirement, Decision, GraphEdge, EdgeType
from app.models.user import User
from app.services.vector_sync import sync_node_to_vector_store
from app.services.search import hybrid_search
from app.database.qdrant import init_qdrant_collections


@pytest.mark.asyncio
async def test_hybrid_search_end_to_end():
    # Initialize SQL database tables
    await init_db()

    # 1. Initialize Qdrant collections if they don't exist
    await init_qdrant_collections()

    # 2. Get database session
    async with async_session() as db:
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            email=f"test_user_{uuid.uuid4().hex[:6]}@example.com",
            display_name="Test User"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create a test project
        project = Project(
            id=uuid.uuid4(),
            name=f"Search Test Project {uuid.uuid4().hex[:6]}",
            description="Testing Hybrid Search and BFS enrichment",
            owner_id=user.id
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Create a mock requirement
        requirement = Requirement(
            id=uuid.uuid4(),
            project_id=project.id,
            title="SSO Authentication Support",
            description="The system must support secure Google SSO authentication login workflow.",
            confidence=0.95
        )
        db.add(requirement)

        # Create a mock decision
        decision = Decision(
            id=uuid.uuid4(),
            project_id=project.id,
            title="Use FastAPI for Backend Framework",
            rationale="We decided to use FastAPI because of its excellent support for async operations and automatic OpenAPI/Swagger documentation.",
            confidence=0.98
        )
        db.add(decision)
        await db.commit()
        await db.refresh(requirement)
        await db.refresh(decision)

        # Create an edge linking Requirement to Decision (Justified By)
        edge = GraphEdge(
            project_id=project.id,
            source_type="requirements",
            source_id=requirement.id,
            target_type="decisions",
            target_id=decision.id,
            edge_type=EdgeType.JUSTIFIED_BY,
            weight=1.0,
            description="The decision to use FastAPI justifies our SSO backend strategy."
        )
        db.add(edge)
        await db.commit()

        # 3. Synchronize nodes to Qdrant (generates Gemini embeddings and upserts)
        # We search with Gemini embeddings
        sync_req = await sync_node_to_vector_store(
            collection_name="requirements",
            node_id=requirement.id,
            project_id=project.id,
            node_type="requirements",
            content=f"{requirement.title}: {requirement.description}",
            metadata={"title": requirement.title}
        )
        assert sync_req is True, "Failed to sync Requirement to Qdrant"

        sync_dec = await sync_node_to_vector_store(
            collection_name="decisions",
            node_id=decision.id,
            project_id=project.id,
            node_type="decisions",
            content=f"{decision.title}: {decision.rationale}",
            metadata={"title": decision.title}
        )
        assert sync_dec is True, "Failed to sync Decision to Qdrant"

        # 4. Perform Hybrid Search
        # Keyword Search Match
        results_keyword = await hybrid_search(
            db=db,
            query="SSO Authentication",
            project_id=project.id,
            limit=5
        )
        assert len(results_keyword) > 0, "No results found for keyword query"
        assert results_keyword[0].node_id == requirement.id, "SSO Requirement should be the top match"
        
        # Verify BFS Graph Context Enrichment
        ctx = results_keyword[0].graph_context
        assert ctx is not None, "Graph context should be enriched"
        assert len(ctx.get("outgoing_edges", [])) > 0, "SSO Requirement should have an outgoing edge to Decision"
        assert ctx["outgoing_edges"][0]["type"] == "justified_by"
        assert ctx["outgoing_edges"][0]["target"] == str(decision.id)

        # Semantic Search Match (using a synonym or semantic idea like "login system credentials")
        results_semantic = await hybrid_search(
            db=db,
            query="login system credentials",
            project_id=project.id,
            limit=5
        )
        assert len(results_semantic) > 0, "No results found for semantic query"
        assert results_semantic[0].node_id == requirement.id, "Semantic match should resolve to SSO requirement"

        # 5. Test the FastAPI Search API Route
        from app.main import app
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/search/",
                params={
                    "q": "SSO Authentication",
                    "project_id": str(project.id),
                    "limit": 5
                }
            )
            assert response.status_code == 200, f"API query failed: {response.text}"
            data = response.json()
            assert "results" in data
            assert data["count"] > 0
            
            top_hit = data["results"][0]
            assert top_hit["node_id"] == str(requirement.id), "Top API result node ID mismatch"
            assert top_hit["node_type"] == "requirements", "Top API result node type mismatch"
            assert "graph_context" in top_hit, "API result missing graph context"
            assert len(top_hit["graph_context"].get("outgoing_edges", [])) > 0, "API result missing graph context edges"
            assert top_hit["graph_context"]["outgoing_edges"][0]["type"] == "justified_by"

        print("\n=== HYBRID SEARCH & API ROUTE VERIFIED SUCCESSFULLY ===")
        print(f"Query: 'SSO Authentication'")
        print(f"Top Hit: {results_keyword[0].title} (Type: {results_keyword[0].node_type})")
        print(f"Linked Nodes (BFS): {results_keyword[0].graph_context}")
