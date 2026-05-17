"""
AI Chat & RAG routes — conversational queries and multi-turn context support.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.chat import retrieve_and_generate, chat_sessions, get_or_create_session

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
    
    Performs hybrid context retrieval, graph context enrichment, and synthesizes 
    a highly precise markdown answer with inline citations and a confidence score.
    """
    try:
        pid = uuid.UUID(payload.project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id UUID format")

    # Generate session ID if not provided
    session_id = payload.session_id or str(uuid.uuid4())

    # Execute the RAG pipeline
    result = await retrieve_and_generate(
        db=db,
        query=payload.query,
        project_id=pid,
        session_id=session_id,
        limit=payload.limit
    )

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
        ]
    }


@router.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """Retrieve all conversation turns inside a active chat session."""
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
