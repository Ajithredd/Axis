"""Intelligence Graph models — Requirement, Decision, Stakeholder, and GraphEdge.

These models extend the existing Feature/Event schema to form the
Feature Intelligence Graph — a knowledge graph that captures the full
context of every software feature: its requirements, the decisions that
shaped it, the stakeholders involved, and the evidence trail linking
everything together.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    String, DateTime, ForeignKey, Text, Enum, Float, Integer,
    UniqueConstraint, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RequirementType(str, PyEnum):
    """Classification of a requirement."""
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"
    ASSUMPTION = "assumption"


class RequirementStatus(str, PyEnum):
    """Lifecycle status of a requirement."""
    DRAFT = "draft"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"


class DecisionStatus(str, PyEnum):
    """Lifecycle status of a decision."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class StakeholderRole(str, PyEnum):
    """Role a stakeholder plays in a project."""
    DEVELOPER = "developer"
    QA = "qa"
    PRODUCT_OWNER = "product_owner"
    DESIGNER = "designer"
    CLIENT = "client"
    ARCHITECT = "architect"
    DEVOPS = "devops"


class EdgeType(str, PyEnum):
    """Semantic type of a graph edge."""
    # Feature ↔ Requirement
    REQUIRES = "requires"
    # Feature ↔ Decision
    DECIDED_BY = "decided_by"
    # Feature ↔ Event (code commits, MRs, etc.)
    IMPLEMENTED_BY = "implemented_by"
    # Requirement ↔ Decision
    JUSTIFIED_BY = "justified_by"
    # Requirement ↔ Requirement
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    # Stakeholder ↔ Feature/Requirement/Decision
    AUTHORED = "authored"
    REVIEWED = "reviewed"
    APPROVED_BY = "approved_by"
    # Generic evidence link
    EVIDENCED_BY = "evidenced_by"


# ---------------------------------------------------------------------------
# Core Graph Entities
# ---------------------------------------------------------------------------

class Requirement(Base):
    """
    A captured software requirement derived from project activity.

    Requirements are extracted (by the LLM classifier) from issues,
    discussions, and documentation, then linked to the Feature they
    belong to via GraphEdge.
    """
    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    requirement_type: Mapped[RequirementType] = mapped_column(
        Enum(RequirementType), default=RequirementType.FUNCTIONAL
    )
    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus), default=RequirementStatus.DRAFT
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # AI confidence that this is a genuine requirement (0.0–1.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Source traceability — the event from which this requirement was extracted
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=True
    )

    # Arbitrary structured data (acceptance criteria, tags, etc.)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship()
    source_event: Mapped["Event | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Requirement {self.title!r} ({self.status.value})>"


class Decision(Base):
    """
    An architectural or product decision captured from project activity.

    Decisions are extracted from merge-request reviews, Slack threads,
    meeting notes, etc. Each decision is linked to the requirements
    and features it influences via GraphEdge.
    """
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    title: Mapped[str] = mapped_column(String(500))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternatives_considered: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus), default=DecisionStatus.PROPOSED
    )

    # AI confidence (0.0–1.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Source traceability
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=True
    )

    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship()
    source_event: Mapped["Event | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Decision {self.title!r} ({self.status.value})>"


class Stakeholder(Base):
    """
    A person or team involved in a project, resolved from actor data.

    Stakeholders are deduplicated across connectors — the same person
    appearing in GitLab and Slack is linked to a single Stakeholder node.
    """
    __tablename__ = "stakeholders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    role: Mapped[StakeholderRole] = mapped_column(
        Enum(StakeholderRole), default=StakeholderRole.DEVELOPER
    )

    # Cross-system identity mapping
    external_ids: Mapped[dict] = mapped_column(
        JSONB, default=dict,
        comment='e.g. {"gitlab_username": "alice", "slack_user_id": "U123"}'
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship()

    __table_args__ = (
        UniqueConstraint("project_id", "email", name="uq_stakeholder_project_email"),
    )

    def __repr__(self) -> str:
        return f"<Stakeholder {self.display_name} ({self.role.value})>"


# ---------------------------------------------------------------------------
# Graph Edge (the connective tissue)
# ---------------------------------------------------------------------------

class GraphEdge(Base):
    """
    A typed, weighted edge between any two nodes in the Intelligence Graph.

    This is the universal join table that connects Features, Requirements,
    Decisions, Stakeholders, and Events into a traversable knowledge graph.

    source_type / target_type hold the table name of the linked entity
    (e.g. "features", "requirements", "decisions", "events", "stakeholders").
    """
    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )

    # Source node
    source_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    # Target node
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    # Semantic type of the relationship
    edge_type: Mapped[EdgeType] = mapped_column(Enum(EdgeType))

    # Strength / relevance of the link (0.0–1.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    # Optional description / AI reasoning for why this edge exists
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship()

    __table_args__ = (
        # Prevent exact duplicate edges
        UniqueConstraint(
            "source_type", "source_id", "target_type", "target_id", "edge_type",
            name="uq_graph_edge_pair",
        ),
        # Fast lookups by source or target
        Index("ix_graph_edge_source", "source_type", "source_id"),
        Index("ix_graph_edge_target", "target_type", "target_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<GraphEdge {self.source_type}:{self.source_id} "
            f"--[{self.edge_type.value}]--> "
            f"{self.target_type}:{self.target_id}>"
        )
