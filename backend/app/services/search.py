"""
Search service — semantic search via pgvector.

Embeds the user's query, finds nearest neighbors in the vector store,
and returns results with source attribution.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import Embedding
from app.services.embedding import generate_single_embedding


@dataclass
class SearchResult:
    """A single search result with source attribution."""
    chunk_text: str
    score: float  # Cosine similarity (0-1, higher = more relevant)
    title: str | None
    event_type: str
    connector_type: str
    source_url: str | None
    actor_name: str | None
    source_timestamp: datetime | None
    event_id: uuid.UUID


async def semantic_search(
    db: AsyncSession,
    query: str,
    project_id: uuid.UUID,
    limit: int = 10,
    connector_type: str | None = None,
    event_type: str | None = None,
) -> list[SearchResult]:
    """
    Perform semantic search over project content.

    1. Embed the query text
    2. Find nearest neighbors using pgvector cosine distance
    3. Return results with metadata and source links
    """
    # Generate embedding for the query
    query_vector = await generate_single_embedding(query)
    if not query_vector:
        return []

    # Build the query with pgvector cosine distance operator (<=>)
    # Lower distance = more similar, so we ORDER ASC
    vector_str = f"[{','.join(str(v) for v in query_vector)}]"

    conditions = ["e.project_id = :project_id"]
    params = {"project_id": str(project_id), "limit": limit}

    if connector_type:
        conditions.append("e.connector_type = :connector_type")
        params["connector_type"] = connector_type

    if event_type:
        conditions.append("e.event_type LIKE :event_type")
        params["event_type"] = f"{event_type}%"

    where_clause = " AND ".join(conditions)

    query_sql = text(f"""
        SELECT
            e.id,
            e.chunk_text,
            e.title,
            e.event_type,
            e.connector_type,
            e.source_url,
            e.actor_name,
            e.source_timestamp,
            e.event_id,
            1 - (e.vector <=> '{vector_str}'::vector) AS similarity
        FROM embeddings e
        WHERE {where_clause}
        ORDER BY e.vector <=> '{vector_str}'::vector
        LIMIT :limit
    """)

    result = await db.execute(query_sql, params)
    rows = result.fetchall()

    return [
        SearchResult(
            chunk_text=row.chunk_text,
            score=float(row.similarity),
            title=row.title,
            event_type=row.event_type,
            connector_type=row.connector_type,
            source_url=row.source_url,
            actor_name=row.actor_name,
            source_timestamp=row.source_timestamp,
            event_id=row.event_id,
        )
        for row in rows
    ]
