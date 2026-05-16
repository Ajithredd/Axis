"""Event model — immutable event log. All connectors emit normalized events."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON, Text, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Event(Base):
    """
    A normalized, immutable event from any connector.

    Every piece of content from GitLab, Slack, Confluence, email, etc.
    gets stored as an Event with a common schema. This is the core
    of Axis's organizational memory.

    event_type examples:
      - "issue.created", "issue.updated", "issue.commented"
      - "merge_request.opened", "merge_request.merged"
      - "commit.pushed"
      - "message.sent" (Slack)
      - "page.updated" (Confluence)
      - "email.received"
    """
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    # --- Source identification ---
    # Which connector produced this event
    connector_type: Mapped[str] = mapped_column(String(50), index=True)

    # Unique ID in the source system (e.g., GitLab issue IID, Slack message ts)
    source_id: Mapped[str] = mapped_column(String(255), index=True)

    # URL back to the source (e.g., GitLab issue URL)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # --- Event classification ---
    # Normalized event type (e.g., "issue.created", "merge_request.commented")
    event_type: Mapped[str] = mapped_column(String(100), index=True)

    # --- Content ---
    # The main text content (issue body, comment text, commit message, etc.)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Actor ---
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- Extra data ---
    # Connector-specific data as JSON
    # GitLab: {"labels": [...], "milestone": "v1.0", "state": "opened", "iid": 42}
    # Slack:  {"channel": "#dev", "thread_ts": "...", "reactions": [...]}
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    # --- Timestamps ---
    # When the event occurred in the source system
    source_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    # When we ingested it
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # --- Relationships ---
    project: Mapped["Project"] = relationship(back_populates="events")
    embeddings: Mapped[list["Embedding"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} from {self.connector_type}: {self.title}>"

    @property
    def searchable_text(self) -> str:
        """Combine title + content for embedding."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.content:
            parts.append(self.content)
        return "\n\n".join(parts)
