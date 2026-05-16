"""Feature model — auto-detected logical features and their linked events."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, Text, Enum, Float, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeatureStatus(str, PyEnum):
    """Detected status of a feature."""
    ACTIVE = "active"
    COMPLETED = "completed"
    STALE = "stale"
    CONFLICTED = "conflicted"


class Feature(Base):
    """
    An auto-detected logical feature that clusters related events.

    The AI classifier groups issues, MRs, comments, etc. into
    logical features (e.g., "Authentication Flow", "Payment Integration").
    """
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FeatureStatus] = mapped_column(
        Enum(FeatureStatus), default=FeatureStatus.ACTIVE
    )

    # AI confidence score (0.0 - 1.0) for this feature classification
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="features")
    links: Mapped[list["FeatureLink"]] = relationship(
        back_populates="feature", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Feature {self.name} ({self.status.value})>"


class FeatureLink(Base):
    """Links an Event to a Feature with a relevance score."""
    __tablename__ = "feature_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id"), index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), index=True
    )

    # How relevant is this event to the feature (0.0 - 1.0)
    relevance: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    feature: Mapped["Feature"] = relationship(back_populates="links")
    event: Mapped["Event"] = relationship()

    def __repr__(self) -> str:
        return f"<FeatureLink feature={self.feature_id} event={self.event_id}>"
