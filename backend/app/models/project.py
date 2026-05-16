"""Project model — a connected project with one or more connector sources."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, JSON, Enum, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SyncStatus(str, PyEnum):
    """Status of the connector sync for a project."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


class Project(Base):
    """A Axis project — groups content from one or more connected sources."""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="projects")
    connectors: Mapped[list["ProjectConnector"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(back_populates="project")
    features: Mapped[list["Feature"]] = relationship(back_populates="project")

    def __repr__(self) -> str:
        return f"<Project {self.name}>"


class ProjectConnector(Base):
    """
    A connector instance linking a Project to an external source.

    This is the plugin join table — each row represents one connection:
      - Project "MyApp" → GitLab (gitlab.com/org/myapp)
      - Project "MyApp" → Slack (#myapp-dev channel)
      - Project "MyApp" → Confluence (MyApp space)

    Any future integration just adds a new row here.
    """
    __tablename__ = "project_connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )

    # Which connector type (e.g., "gitlab", "slack", "confluence", "email")
    connector_type: Mapped[str] = mapped_column(String(50), index=True)

    # Connector-specific config (e.g., {"gitlab_project_id": 12345, "namespace": "org/repo"})
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Auth tokens specific to this connector instance
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sync state
    sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus), default=SyncStatus.PENDING
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Webhook secret for verifying incoming webhooks
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="connectors")

    def __repr__(self) -> str:
        return f"<ProjectConnector {self.connector_type} for {self.project_id}>"
