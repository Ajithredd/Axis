import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, init_db
from app.models.project import Project
from app.models.user import User
from app.models.graph import Requirement
from app.database.qdrant import init_qdrant_collections
from app.services.vector_sync import sync_node_to_vector_store
from app.services.chat import retrieve_and_generate, chat_sessions


@pytest.mark.asyncio
async def test_chat_and_rag_pipeline():
    # 1. Initialize DB and Qdrant
    await init_db()
    await init_qdrant_collections()

    async with async_session() as db:
        # Create user
        user = User(
            id=uuid.uuid4(),
            email=f"chat_test_{uuid.uuid4().hex[:6]}@example.com",
            display_name="Chat User"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create project
        project = Project(
            id=uuid.uuid4(),
            name=f"Chat Test Project {uuid.uuid4().hex[:6]}",
            description="Testing AI Chat and Citation synthesis",
            owner_id=user.id
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Create requirement
        requirement = Requirement(
            id=uuid.uuid4(),
            project_id=project.id,
            title="SSO Authentication Support",
            description="The system must support secure Google SSO authentication login workflow.",
            confidence=0.95
        )
        db.add(requirement)
        await db.commit()
        await db.refresh(requirement)

        # Synchronize node to vector store
        sync_ok = await sync_node_to_vector_store(
            collection_name="requirements",
            node_id=requirement.id,
            project_id=project.id,
            node_type="requirements",
            content=f"{requirement.title}: {requirement.description}",
            metadata={"title": requirement.title}
        )
        assert sync_ok is True

        # Mock the external Gemini client to return a predictable, valid structured output
        mock_response_json = (
            f'{{"answer": "We support security via [1] SSO authentication.", '
            f'"confidence_score": 0.98, '
            f'"citations": [{{"key": 1, "node_id": "{requirement.id}", '
            f'"node_type": "requirements", "title": "SSO Authentication Support", "url": null}}]}}'
        )

        with patch("app.services.chat.genai.Client") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_generate = AsyncMock()
            mock_client.aio.models.generate_content = mock_generate
            
            mock_response_obj = MagicMock()
            mock_response_obj.text = mock_response_json
            mock_generate.return_value = mock_response_obj

            # Clear session
            session_id = f"session-{uuid.uuid4()}"
            if session_id in chat_sessions:
                del chat_sessions[session_id]

            # 2. Test RAG service layer
            result = await retrieve_and_generate(
                db=db,
                query="How is authentication supported?",
                project_id=project.id,
                session_id=session_id,
                limit=5
            )

            assert "We support security" in result.answer
            assert result.confidence_score == 0.98
            assert len(result.citations) == 1
            assert result.citations[0].node_id == str(requirement.id)
            assert result.citations[0].title == "SSO Authentication Support"

            # 3. Test HTTP API integration
            from app.main import app
            import httpx
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                # Query endpoint
                response = await ac.post(
                    "/api/chat/query",
                    json={
                        "query": "How is authentication supported?",
                        "project_id": str(project.id),
                        "session_id": session_id,
                        "limit": 5
                    }
                )
                assert response.status_code == 200, f"Query endpoint failed: {response.text}"
                data = response.json()
                assert "answer" in data
                assert data["confidence_score"] == 0.98
                assert len(data["citations"]) == 1
                assert data["citations"][0]["node_id"] == str(requirement.id)

                # Get session history
                history_resp = await ac.get(f"/api/chat/session/{session_id}")
                assert history_resp.status_code == 200
                history_data = history_resp.json()
                assert history_data["count"] > 0
                assert history_data["history"][0]["role"] == "user"

                # Clear session endpoint
                clear_resp = await ac.post("/api/chat/session/clear", json={"session_id": session_id})
                assert clear_resp.status_code == 200
                assert chat_sessions[session_id] == []

        print("\n=== AI CONVERSATIONAL RAG & CITATIONS TEST PASSED ===")
