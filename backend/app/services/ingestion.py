"""
Ingestion service — orchestrates connector sync → event storage → embeddings.

This is the pipeline:
  1. Connector fetches data → NormalizedEvents
  2. Events are stored in the immutable event log
  3. Each event's text is chunked and embedded
  4. Embeddings are stored in Qdrant for semantic search
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.event import Event
from app.models.project import ProjectConnector, SyncStatus
from app.connectors.base import NormalizedEvent
from app.connectors.registry import connector_registry
from app.services.embedding import chunk_text, content_hash
from app.services.vector_sync import sync_node_to_vector_store
from app.services.graph_ingestion import GraphIngestionEngine


async def ingest_project(
    db: AsyncSession,
    project_connector: ProjectConnector,
) -> dict:
    """
    Run a full sync for a project connector.

    Fetches all data from the source, stores events, generates embeddings.
    Returns a summary of what was ingested.
    """
    connector = connector_registry.get(project_connector.connector_type)
    if not connector:
        raise ValueError(f"Unknown connector type: {project_connector.connector_type}")

    # Update sync status
    project_connector.sync_status = SyncStatus.SYNCING
    await db.flush()

    try:
        # Fetch events from the connector
        normalized_events = await connector.sync_all(
            config=project_connector.config,
            access_token=project_connector.access_token or "",
            since=project_connector.last_synced_at,
        )

        # Process events
        stats = {"events_created": 0, "events_skipped": 0, "embeddings_created": 0, "graph_updates": 0}

        graph_engine = GraphIngestionEngine(db)

        for norm_event in normalized_events:
            # Check for duplicates by source_id
            existing = await db.execute(
                select(Event).where(
                    Event.project_id == project_connector.project_id,
                    Event.source_id == norm_event.source_id,
                )
            )
            if existing.scalar_one_or_none():
                stats["events_skipped"] += 1
                continue

            # Create event record
            event = Event(
                project_id=project_connector.project_id,
                connector_type=norm_event.connector_type,
                source_id=norm_event.source_id,
                source_url=norm_event.source_url,
                event_type=norm_event.event_type,
                title=norm_event.title,
                content=norm_event.content,
                actor_name=norm_event.actor_name,
                actor_email=norm_event.actor_email,
                source_timestamp=norm_event.source_timestamp,
                extra=norm_event.extra,
            )
            db.add(event)
            await db.flush()  # Get the event ID
            stats["events_created"] += 1

            # Generate embeddings and sync to Qdrant
            text = event.searchable_text
            if text:
                chunks = chunk_text(
                    text,
                    chunk_size=settings.child_chunk_size,
                    chunk_overlap=settings.child_chunk_overlap,
                )
                if chunks:
                    embeddings_created = await _embed_chunks_to_qdrant(
                        event=event,
                        chunks=chunks,
                    )
                    stats["embeddings_created"] += embeddings_created

            # Hook: process event into Intelligence Graph
            try:
                graph_stats = await graph_engine.process_event(event)
                stats["graph_updates"] += sum(graph_stats.values())
            except Exception as e:
                # Graph enrichment is non-blocking — log and continue
                import logging
                logging.getLogger(__name__).warning(
                    f"Graph ingestion failed for event {event.id}: {e}"
                )

        # Update sync status
        project_connector.sync_status = SyncStatus.SYNCED
        project_connector.last_synced_at = datetime.utcnow()
        project_connector.sync_error = None
        await db.commit()

        return stats

    except Exception as e:
        project_connector.sync_status = SyncStatus.FAILED
        project_connector.sync_error = str(e)
        await db.commit()
        raise


async def ingest_webhook_events(
    db: AsyncSession,
    project_id: uuid.UUID,
    normalized_events: list[NormalizedEvent],
) -> dict:
    """
    Process events received via webhook.
    Same logic as full sync but for individual events.
    """
    stats = {"events_created": 0, "events_updated": 0, "embeddings_created": 0, "graph_updates": 0}

    graph_engine = GraphIngestionEngine(db)

    for norm_event in normalized_events:
        # Check for existing event (upsert logic)
        result = await db.execute(
            select(Event).where(
                Event.project_id == project_id,
                Event.source_id == norm_event.source_id,
            )
        )
        existing_event = result.scalar_one_or_none()

        if existing_event:
            # Update existing event
            existing_event.title = norm_event.title
            existing_event.content = norm_event.content
            existing_event.event_type = norm_event.event_type
            existing_event.extra = norm_event.extra
            existing_event.source_timestamp = norm_event.source_timestamp
            stats["events_updated"] += 1

            # Re-embed if content changed
            text = existing_event.searchable_text
            if text:
                chunks = chunk_text(
                    text,
                    chunk_size=settings.child_chunk_size,
                    chunk_overlap=settings.child_chunk_overlap,
                )
                if chunks:
                    count = await _embed_chunks_to_qdrant(existing_event, chunks)
                    stats["embeddings_created"] += count
        else:
            # Create new event
            event = Event(
                project_id=project_id,
                connector_type=norm_event.connector_type,
                source_id=norm_event.source_id,
                source_url=norm_event.source_url,
                event_type=norm_event.event_type,
                title=norm_event.title,
                content=norm_event.content,
                actor_name=norm_event.actor_name,
                actor_email=norm_event.actor_email,
                source_timestamp=norm_event.source_timestamp,
                extra=norm_event.extra,
            )
            db.add(event)
            await db.flush()
            stats["events_created"] += 1

            text = event.searchable_text
            if text:
                chunks = chunk_text(
                    text,
                    chunk_size=settings.child_chunk_size,
                    chunk_overlap=settings.child_chunk_overlap,
                )
                if chunks:
                    count = await _embed_chunks_to_qdrant(event, chunks)
                    stats["embeddings_created"] += count

            # Hook: process event into Intelligence Graph
            try:
                graph_stats = await graph_engine.process_event(event)
                stats["graph_updates"] += sum(graph_stats.values())
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Graph ingestion failed for event {event.id}: {e}"
                )

    await db.commit()
    return stats


async def _embed_chunks_to_qdrant(
    event: Event,
    chunks: list[str],
) -> int:
    """Generate embeddings via Qdrant vector_sync for text chunks.

    Each chunk is upserted to the ``events`` Qdrant collection with a
    deterministic UUID derived from event ID + chunk index so that
    re-indexing the same event naturally overwrites old points.
    """
    import logging
    logger = logging.getLogger(__name__)
    count = 0

    for i, chunk in enumerate(chunks):
        # Deterministic UUID: same event + chunk index = same point ID
        chunk_id = uuid.uuid5(event.id, f"chunk-{i}")
        try:
            ok = await sync_node_to_vector_store(
                collection_name="events",
                node_id=chunk_id,
                project_id=event.project_id,
                node_type="events",
                content=chunk,
                metadata={
                    "title": event.title,
                    "event_type": event.event_type,
                    "source_url": event.source_url,
                    "actor_name": event.actor_name,
                    "chunk_index": i,
                    "parent_event_id": str(event.id),
                    "content_hash": content_hash(chunk),
                },
            )
            if ok:
                count += 1
        except Exception as e:
            logger.error(f"Failed to sync event chunk {i} for event {event.id}: {e}")

    return count
