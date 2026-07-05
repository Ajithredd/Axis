"""
AI Chat & RAG routes — conversational queries, multi-turn context support,
and retrieval quality evaluation endpoints.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.chat import retrieve_and_generate, chat_sessions, get_or_create_session, RAGMetrics
from dataclasses import asdict

router = APIRouter()


class ChatQueryRequest(BaseModel):
    """Payload schema for executing a conversational RAG query."""
    query: str = Field(..., min_length=1, description="Conversational query or question")
    project_id: str = Field(..., description="UUID of the project workspace context")
    session_id: Optional[str] = Field(None, description="Optional conversation session ID to persist history")
    limit: int = Field(5, ge=1, le=20, description="Max search results to retrieve as factual context")


class SessionClearRequest(BaseModel):
    """Payload to reset a conversational session."""
    session_id: str = Field(..., description="The session ID to reset")


@router.post("/query")
async def chat_query(
    payload: ChatQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a query to the AI Alignment Chat Agent.

    Performs hybrid context retrieval with advanced retrieval strategies
    (Step-Back Prompting, Parent-Document Retrieval, Contextual Compression),
    graph context enrichment, and synthesizes a highly precise markdown
    answer with inline citations and a confidence score.

    The response includes:
    - `rag_metrics`: Full pipeline metrics (latency, retrieval eval, RAGAS scores)
    - `ragas_eval`: Convenience object with just the RAGAS scores
    """
    try:
        pid = uuid.UUID(payload.project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id UUID format")

    # Generate session ID if not provided
    session_id = payload.session_id or str(uuid.uuid4())

    # Execute the RAG pipeline
    result, metrics = await retrieve_and_generate(
        db=db,
        query=payload.query,
        project_id=pid,
        session_id=session_id,
        limit=payload.limit
    )

    metrics_dict = asdict(metrics)

    return {
        "session_id": session_id,
        "answer": result.answer,
        "confidence_score": round(result.confidence_score, 4),
        "citations": [
            {
                "key": c.key,
                "node_id": c.node_id,
                "node_type": c.node_type,
                "title": c.title,
                "url": c.url,
                "snippet": c.snippet
            }
            for c in result.citations
        ],
        "rag_metrics": metrics_dict,
        # Convenience: top-level RAGAS scores for the frontend eval badge
        "ragas_eval": {
            "faithfulness": metrics.ragas_faithfulness,
            "answer_relevancy": metrics.ragas_answer_relevancy,
            "context_precision": metrics.ragas_context_precision,
            "context_recall": metrics.ragas_context_recall,
            "context_entity_recall": metrics.ragas_context_entity_recall,
            "ragas_score": metrics.ragas_score,
            "evaluated": metrics.ragas_evaluated,
            "error": metrics.ragas_error,
        },
        # Convenience: advanced retrieval summary
        "advanced_retrieval": {
            "step_back_used": metrics.step_back_query_used,
            "parent_documents_expanded": metrics.parent_documents_expanded,
            "contextual_compression_applied": metrics.contextual_compression_applied,
        },
    }


@router.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """Retrieve all conversation turns inside an active chat session."""
    history = get_or_create_session(session_id)
    return {
        "session_id": session_id,
        "history": history,
        "count": len(history)
    }


@router.post("/session/clear")
async def clear_session(payload: SessionClearRequest):
    """Reset / clear conversational history logs of a specific chat session."""
    if payload.session_id in chat_sessions:
        chat_sessions[payload.session_id] = []
        return {"status": "success", "detail": f"Session {payload.session_id} history cleared"}
    return {"status": "noop", "detail": "Session ID not found"}
