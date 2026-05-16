"""
Search routes — semantic search across all project content.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.search import semantic_search

router = APIRouter()


@router.get("/")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    project_id: str = Query(..., description="Project ID to search within"),
    connector_type: str | None = Query(None, description="Filter by connector type"),
    event_type: str | None = Query(None, description="Filter by event type prefix"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search across all project content.

    Returns ranked results with source attribution — each result
    links back to its source (GitLab issue, Slack message, etc.).
    """
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(400, "Invalid project ID")

    results = await semantic_search(
        db=db,
        query=q,
        project_id=pid,
        limit=limit,
        connector_type=connector_type,
        event_type=event_type,
    )

    return {
        "query": q,
        "results": [
            {
                "text": r.chunk_text,
                "score": round(r.score, 4),
                "title": r.title,
                "event_type": r.event_type,
                "connector_type": r.connector_type,
                "source_url": r.source_url,
                "actor": r.actor_name,
                "timestamp": r.source_timestamp.isoformat() if r.source_timestamp else None,
            }
            for r in results
        ],
        "count": len(results),
    }
