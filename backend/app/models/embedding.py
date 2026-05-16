"""Embedding model — pgvector storage for semantic search."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.config import settings
from app.database import Base


class Embedding(Base):
    """
    A vector embedding of a text chunk from an Event.

    Large events get split into chunks, each stored with its own
    embedding vector for semantic search via pgvector.
    """
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), index=True
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    # The text chunk that was embedded
    chunk_text: Mapped[str] = mapped_column(Text)

    # Chunk position within the event (0-indexed)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    # The vector embedding (dimension matches EMBEDDING_DIMENSIONS in config)
    vector = mapped_column(Vector(settings.embedding_dimensions))

    # Content hash for deduplication
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    # Denormalized metadata for fast filtering during search
    connector_type: Mapped[str] = mapped_column(String(50), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="embeddings")

    def __repr__(self) -> str:
        return f"<Embedding chunk {self.chunk_index} of event {self.event_id}>"
