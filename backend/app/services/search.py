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
from app.models.graph import Requirement, Decision, Stakeholder
from app.models.feature import Feature
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
    collections = ["requirements", "decisions", "events", "features", "stakeholders"]
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
    """Perform full-text search across Postgres tables using tsvector and websearch_to_tsquery."""
    from sqlalchemy import func

    if not query or not query.strip():
        return []

    collections = ["requirements", "decisions", "events", "features", "stakeholders"]
    if node_types:
        collections = [c for c in collections if c in node_types]

    all_results = []
    # Use websearch_to_tsquery for robust Google-like search syntax parsing
    ts_query = func.websearch_to_tsquery("english", query)

    if "requirements" in collections:
        # Title has weight 'A' (1.0), description has weight 'B' (0.4)
        from sqlalchemy import literal_column
        ts_vector = (
            func.setweight(func.to_tsvector("english", func.coalesce(Requirement.title, "")), literal_column("'A'::\"char\"")).op("||")(
            func.setweight(func.to_tsvector("english", func.coalesce(Requirement.description, "")), literal_column("'B'::\"char\"")))
        )
        stmt = select(
            Requirement,
            func.ts_rank_cd(ts_vector, ts_query).label("score")
        ).where(
            Requirement.project_id == project_id,
            ts_vector.op("@@")(ts_query)
        ).order_by(func.ts_rank_cd(ts_vector, ts_query).desc()).limit(limit)

        res = await db.execute(stmt)
        for req, score in res.all():
            all_results.append({
                "id": str(req.id),
                "title": req.title,
                "content": req.description or "",
                "node_type": "requirements",
                "project_id": str(req.project_id),
                "score": float(score)
            })

    if "decisions" in collections:
        from sqlalchemy import literal_column
        ts_vector = (
            func.setweight(func.to_tsvector("english", func.coalesce(Decision.title, "")), literal_column("'A'::\"char\"")).op("||")(
            func.setweight(func.to_tsvector("english", func.coalesce(Decision.rationale, "")), literal_column("'B'::\"char\"")))
        )
        stmt = select(
            Decision,
            func.ts_rank_cd(ts_vector, ts_query).label("score")
        ).where(
            Decision.project_id == project_id,
            ts_vector.op("@@")(ts_query)
        ).order_by(func.ts_rank_cd(ts_vector, ts_query).desc()).limit(limit)

        res = await db.execute(stmt)
        for dec, score in res.all():
            all_results.append({
                "id": str(dec.id),
                "title": dec.title,
                "content": dec.rationale or "",
                "node_type": "decisions",
                "project_id": str(dec.project_id),
                "score": float(score)
            })

    if "events" in collections:
        from sqlalchemy import literal_column
        ts_vector = (
            func.setweight(func.to_tsvector("english", func.coalesce(Event.title, "")), literal_column("'A'::\"char\"")).op("||")(
            func.setweight(func.to_tsvector("english", func.coalesce(Event.content, "")), literal_column("'B'::\"char\"")))
        )
        stmt = select(
            Event,
            func.ts_rank_cd(ts_vector, ts_query).label("score")
        ).where(
            Event.project_id == project_id,
            ts_vector.op("@@")(ts_query)
        ).order_by(func.ts_rank_cd(ts_vector, ts_query).desc()).limit(limit)

        res = await db.execute(stmt)
        for ev, score in res.all():
            all_results.append({
                "id": str(ev.id),
                "title": ev.title,
                "content": ev.content or "",
                "node_type": "events",
                "project_id": str(ev.project_id),
                "score": float(score)
            })

    if "features" in collections:
        from sqlalchemy import literal_column
        ts_vector = (
            func.setweight(func.to_tsvector("english", func.coalesce(Feature.name, "")), literal_column("'A'::\"char\"")).op("||")(
            func.setweight(func.to_tsvector("english", func.coalesce(Feature.description, "")), literal_column("'B'::\"char\"")))
        )
        stmt = select(
            Feature,
            func.ts_rank_cd(ts_vector, ts_query).label("score")
        ).where(
            Feature.project_id == project_id,
            ts_vector.op("@@")(ts_query)
        ).order_by(func.ts_rank_cd(ts_vector, ts_query).desc()).limit(limit)

        res = await db.execute(stmt)
        for feat, score in res.all():
            all_results.append({
                "id": str(feat.id),
                "title": feat.name,
                "content": feat.description or "",
                "node_type": "features",
                "project_id": str(feat.project_id),
                "score": float(score)
            })

    if "stakeholders" in collections:
        from sqlalchemy import literal_column
        ts_vector = (
            func.setweight(func.to_tsvector("english", func.coalesce(Stakeholder.display_name, "")), literal_column("'A'::\"char\"")).op("||")(
            func.setweight(func.to_tsvector("english", func.coalesce(Stakeholder.email, "")), literal_column("'B'::\"char\"")))
        )
        stmt = select(
            Stakeholder,
            func.ts_rank_cd(ts_vector, ts_query).label("score")
        ).where(
            Stakeholder.project_id == project_id,
            ts_vector.op("@@")(ts_query)
        ).order_by(func.ts_rank_cd(ts_vector, ts_query).desc()).limit(limit)

        res = await db.execute(stmt)
        for sh, score in res.all():
            all_results.append({
                "id": str(sh.id),
                "title": sh.display_name,
                "content": f"{sh.display_name} ({sh.role.value})" + (f" - {sh.email}" if sh.email else ""),
                "node_type": "stakeholders",
                "project_id": str(sh.project_id),
                "score": float(score)
            })

    all_results.sort(key=lambda x: x["score"], reverse=True)
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
                    "project_id": str(res.get("project_id", "")),
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


def deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    """
    Deduplicate search results based on exact content match or high title similarity.
    Keeps the highest scoring result for each unique document.
    """
    seen_contents = set()
    unique_results = []

    for res in results:
        content_norm = " ".join((res.content or "").strip().lower().split())
        title_norm = " ".join((res.title or "").strip().lower().split())
        
        # Remove punctuation for better comparison
        punctuation = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
        title_clean = title_norm.translate(str.maketrans('', '', punctuation))

        # Check exact content match
        if content_norm and content_norm in seen_contents:
            logger.info(f"Deduplicating node {res.node_id} due to duplicate content.")
            continue

        # Check title similarity with already accepted results
        duplicate_title = False
        for accepted in unique_results:
            accepted_title_norm = " ".join((accepted.title or "").strip().lower().split())
            accepted_title_clean = accepted_title_norm.translate(str.maketrans('', '', punctuation))
            
            if not title_clean or not accepted_title_clean:
                continue

            # Exact match of cleaned title
            if title_clean == accepted_title_clean:
                duplicate_title = True
                break

            # Word-level Jaccard similarity
            w1 = set(title_clean.split())
            w2 = set(accepted_title_clean.split())
            if w1 and w2:
                jaccard = len(w1.intersection(w2)) / len(w1.union(w2))
                if jaccard >= 0.85:
                    duplicate_title = True
                    break
        
        if duplicate_title:
            logger.info(f"Deduplicating node {res.node_id} due to similar title: '{res.title}'")
            continue

        if content_norm:
            seen_contents.add(content_norm)
        unique_results.append(res)

    return unique_results


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
    # Fetch extra candidates so we can deduplicate them and still return up to limit
    search_limit = max(limit * 2, 20)
    
    semantic_res = await semantic_search_qdrant(query, project_id, search_limit, node_types)
    keyword_res = await keyword_search_postgres(db, query, project_id, search_limit, node_types)

    fused_results = compute_rrf(semantic_res, keyword_res)
    
    final_results = []
    for item in fused_results:
        payload = item.get("payload", {})
        node_id_str = str(item["id"])
        
        try:
            node_id = uuid.UUID(node_id_str)
        except ValueError:
            continue
            
        node_type = payload.get("node_type", "unknown")
        content = payload.get("content", "")

        # Parent-Child Retrieval: If it's an event chunk, resolve the parent event
        if node_type == "events":
            parent_id_str = payload.get("metadata", {}).get("parent_event_id")
            if parent_id_str:
                try:
                    parent_id = uuid.UUID(parent_id_str)
                    stmt = select(Event).where(Event.id == parent_id)
                    db_res = await db.execute(stmt)
                    parent_event = db_res.scalar_one_or_none()
                    if parent_event:
                        node_id = parent_id
                        content = parent_event.content or ""
                except Exception as e:
                    logger.warning(f"Failed to fetch parent event {parent_id_str}: {e}")
        
        # Enrich with graph context (1-degree BFS)
        try:
            graph_data = await get_node_with_edges(db, node_id, node_type=node_type)
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

        title = item.get("title") or payload.get("metadata", {}).get("title")
        if not title or title.lower() in ("untitled", "untitled document"):
            try:
                if node_type == "requirements":
                    db_node = await db.get(Requirement, node_id)
                    if db_node and db_node.title:
                        title = db_node.title
                elif node_type == "decisions":
                    db_node = await db.get(Decision, node_id)
                    if db_node and db_node.title:
                        title = db_node.title
                elif node_type == "events":
                    db_node = await db.get(Event, node_id)
                    if db_node and db_node.title:
                        title = db_node.title
                elif node_type == "features":
                    db_node = await db.get(Feature, node_id)
                    if db_node and db_node.name:
                        title = db_node.name
                elif node_type == "stakeholders":
                    db_node = await db.get(Stakeholder, node_id)
                    if db_node and db_node.display_name:
                        title = db_node.display_name
            except Exception as e:
                logger.warning(f"Failed to fetch fallback title for {node_type} {node_id}: {e}")

        final_results.append(SearchResult(
            node_id=node_id,
            project_id=project_id,
            node_type=node_type,
            content=content,
            score=item["rrf_score"],
            title=title or "Untitled",
            metadata=payload.get("metadata", {}),
            graph_context=graph_context
        ))

    # Apply search result deduplication
    deduplicated = deduplicate_results(final_results)
    return deduplicated[:limit]
