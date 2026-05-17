"""
Search routes — Hybrid search across all project content.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.search import hybrid_search

router = APIRouter()


@router.get("/")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    project_id: str = Query(..., description="Project ID to search within"),
    node_types: Optional[List[str]] = Query(None, description="Filter by graph node types (e.g. requirements, decisions)"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid search across all project content.

    Combines semantic vector search (Qdrant) with full-text keyword search
    (PostgreSQL), scoring them with Reciprocal Rank Fusion (RRF).
    Returns ranked results enriched with their graph context (1-degree connections).
    """
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(400, "Invalid project ID")

    results = await hybrid_search(
        db=db,
        query=q,
        project_id=pid,
        limit=limit,
        node_types=node_types,
    )

    return {
        "query": q,
        "results": [
            {
                "node_id": str(r.node_id),
                "node_type": r.node_type,
                "title": r.title,
                "content": r.content,
                "score": round(r.score, 4),
                "metadata": r.metadata or {},
                "graph_context": r.graph_context or {},
            }
            for r in results
        ],
        "count": len(results),
    }
