"""
Webhook routes — receives real-time events from connected sources.

Connector-agnostic: the URL pattern includes connector_type, so the
same endpoint works for GitLab, Slack, Confluence, etc.

Pattern: POST /api/webhooks/{connector_type}/{project_id}
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import ProjectConnector
from app.connectors.registry import connector_registry
from app.services.ingestion import ingest_webhook_events

router = APIRouter()


@router.post("/{connector_type}/{project_id}")
async def receive_webhook(
    connector_type: str,
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive and process a webhook from any connected source.

    The connector handles verification and normalization.
    """
    connector = connector_registry.get(connector_type)
    if not connector:
        raise HTTPException(404, f"Unknown connector: {connector_type}")

    # Find the project connector to get the webhook secret
    result = await db.execute(
        select(ProjectConnector).where(
            ProjectConnector.project_id == uuid.UUID(project_id),
            ProjectConnector.connector_type == connector_type,
        )
    )
    pc = result.scalar_one_or_none()
    if not pc:
        raise HTTPException(404, "Project connector not found")

    # Parse the webhook payload
    payload = await request.json()
    headers = dict(request.headers)

    # Let the connector handle verification and normalization
    normalized_events = await connector.handle_webhook(
        payload=payload,
        headers=headers,
        webhook_secret=pc.webhook_secret,
    )

    if not normalized_events:
        return {"status": "ignored", "reason": "No relevant events in payload"}

    # Ingest the events
    stats = await ingest_webhook_events(
        db=db,
        project_id=uuid.UUID(project_id),
        normalized_events=normalized_events,
    )

    return {"status": "processed", "stats": stats}
