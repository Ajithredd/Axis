"""
Search service — Hybrid search via Qdrant and PostgreSQL.

Combines semantic vector search (Qdrant) and keyword search (PostgreSQL)
using Reciprocal Rank Fusion (RRF), and enriches results with graph context.
"""

import uuid
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client.http import models

from app.database.qdrant import get_qdrant_client
from app.services.embeddings import embedding_engine
from app.models.graph import Requirement, Decision
from app.models.event import Event
from app.services.graph import get_node_with_edges

logger = logging.getLogger(__name__)

RRF_K = 60


@dataclass
class SearchResult:
    """A single search result combining semantic and keyword matching."""
    node_id: uuid.UUID
    project_id: uuid.UUID
    node_type: str
    content: str
    score: float
    title: str | None = None
    metadata: Dict[str, Any] | None = None
    graph_context: Dict[str, Any] | None = None


async def semantic_search_qdrant(
    query: str,
    project_id: uuid.UUID,
    limit: int = 10,
    node_types: List[str] | None = None
) -> List[dict]:
    """Perform semantic search on Qdrant collections."""
    query_vector = await embedding_engine.generate_embedding(query)
    if not query_vector:
        return []

    client = get_qdrant_client()
    collections = ["requirements", "decisions", "events"]
    if node_types:
        collections = [c for c in collections if c in node_types]

    filter_cond = models.Filter(
        must=[
            models.FieldCondition(
                key="project_id",
                match=models.MatchValue(value=str(project_id))
            )
        ]
    )

    all_results = []
    
    # Query each collection
    for collection in collections:
        try:
            response = await client.query_points(
                collection_name=collection,
                query=query_vector,
                query_filter=filter_cond,
                limit=limit
            )
            for hit in response.points:
                all_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                })
        except Exception as e:
            logger.exception(f"Qdrant search failed for collection {collection}: {e}")
            pass

    # Sort globally by score desc
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:limit]


async def keyword_search_postgres(
    db: AsyncSession,
    query: str,
    project_id: uuid.UUID,
    limit: int = 10,
    node_types: List[str] | None = None
) -> List[dict]:
    """Perform full-text search using ILIKE across Postgres tables."""
    all_results = []
    search_term = f"%{query}%"

    collections = ["requirements", "decisions", "events"]
    if node_types:
        collections = [c for c in collections if c in node_types]

    if "requirements" in collections:
        stmt = select(Requirement).where(
            Requirement.project_id == project_id,
            or_(
                Requirement.title.ilike(search_term),
                Requirement.description.ilike(search_term)
            )
        ).limit(limit)
        res = await db.execute(stmt)
        for req in res.scalars().all():
            all_results.append({
                "id": str(req.id),
                "title": req.title,
                "content": req.description or "",
                "node_type": "requirements"
            })

    if "decisions" in collections:
        stmt = select(Decision).where(
            Decision.project_id == project_id,
            or_(
                Decision.title.ilike(search_term),
                Decision.rationale.ilike(search_term)
            )
        ).limit(limit)
        res = await db.execute(stmt)
        for dec in res.scalars().all():
            all_results.append({
                "id": str(dec.id),
                "title": dec.title,
                "content": dec.rationale or "",
                "node_type": "decisions"
            })

    if "events" in collections:
        stmt = select(Event).where(
            Event.project_id == project_id,
            or_(
                Event.title.ilike(search_term),
                Event.content.ilike(search_term)
            )
        ).limit(limit)
        res = await db.execute(stmt)
        for ev in res.scalars().all():
            all_results.append({
                "id": str(ev.id),
                "title": ev.title,
                "content": ev.content or "",
                "node_type": "events"
            })

    return all_results[:limit]


def compute_rrf(semantic_results: List[dict], keyword_results: List[dict]) -> List[dict]:
    """Fuse results using Reciprocal Rank Fusion."""
    scores = {}
    items = {}

    for rank, res in enumerate(semantic_results):
        node_id = res["id"]
        if node_id not in scores:
            scores[node_id] = 0.0
            items[node_id] = res
        scores[node_id] += 1.0 / (RRF_K + rank)

    for rank, res in enumerate(keyword_results):
        node_id = res["id"]
        if node_id not in scores:
            scores[node_id] = 0.0
            items[node_id] = {
                "id": node_id,
                "payload": {
                    "node_id": node_id,
                    "node_type": res["node_type"],
                    "content": res["content"],
                    "project_id": str(res.get("project_id", "")), # Not fetched, but okay
                },
                "title": res["title"]
            }
        else:
            if "title" not in items[node_id]:
                items[node_id]["title"] = res["title"]
        scores[node_id] += 1.0 / (RRF_K + rank)

    # Sort by RRF score
    fused = []
    for node_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        item = items[node_id]
        item["rrf_score"] = score
        fused.append(item)

    return fused


async def hybrid_search(
    db: AsyncSession,
    query: str,
    project_id: uuid.UUID,
    limit: int = 10,
    node_types: List[str] | None = None
) -> List[SearchResult]:
    """
    Perform hybrid search (Semantic + Keyword) and enrich with graph context.
    """
    semantic_task = semantic_search_qdrant(query, project_id, limit, node_types)
    keyword_task = keyword_search_postgres(db, query, project_id, limit, node_types)

    semantic_res, keyword_res = await asyncio.gather(semantic_task, keyword_task)

    fused_results = compute_rrf(semantic_res, keyword_res)
    fused_results = fused_results[:limit]

    final_results = []
    for item in fused_results:
        payload = item.get("payload", {})
        node_id_str = str(item["id"])
        
        try:
            node_id = uuid.UUID(node_id_str)
        except ValueError:
            continue
            
        node_type = payload.get("node_type", "unknown")
        
        # Enrich with graph context (1-degree BFS)
        try:
            # We need to map 'requirements' -> 'requirement', etc for graph.py
            # But get_node_with_edges might expect the table name or the class name.
            # get_node_with_edges expects Node ID and the actual graph DB lookup.
            # Actually get_node_with_edges(db, node_id) looks up by ID across tables.
            graph_data = await get_node_with_edges(db, node_id)
            graph_context = {
                "incoming_edges": [
                    {"type": e.edge_type.value, "source": str(e.source_id)}
                    for e in graph_data.get("incoming_edges", [])
                ],
                "outgoing_edges": [
                    {"type": e.edge_type.value, "target": str(e.target_id)}
                    for e in graph_data.get("outgoing_edges", [])
                ]
            }
        except Exception:
            graph_context = None

        final_results.append(SearchResult(
            node_id=node_id,
            project_id=project_id,
            node_type=node_type,
            content=payload.get("content", ""),
            score=item["rrf_score"],
            title=item.get("title") or payload.get("metadata", {}).get("title"),
            metadata=payload.get("metadata", {}),
            graph_context=graph_context
        ))

    return final_results
