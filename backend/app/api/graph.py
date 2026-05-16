"""Graph API — Feature Intelligence Graph endpoints.

Provides REST endpoints for:
  - /graph/features/{feature_id}/context — full graph context for a feature
  - /graph/requirements — CRUD for requirements
  - /graph/decisions — CRUD for decisions
  - /graph/edges — manage relationships between graph nodes
  - /graph/traverse — BFS traversal from any node
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.graph import (
    RequirementType, RequirementStatus,
    DecisionStatus, StakeholderRole, EdgeType,
)
from app.services import graph as graph_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RequirementCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(..., max_length=500)
    description: str | None = None
    requirement_type: RequirementType = RequirementType.FUNCTIONAL
    priority: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_event_id: uuid.UUID | None = None
    metadata: dict = Field(default_factory=dict)


class RequirementOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    requirement_type: RequirementType
    status: RequirementStatus
    priority: int
    confidence: float
    source_event_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class DecisionCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(..., max_length=500)
    rationale: str | None = None
    alternatives_considered: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_event_id: uuid.UUID | None = None
    metadata: dict = Field(default_factory=dict)


class DecisionOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    rationale: str | None
    alternatives_considered: str | None
    status: DecisionStatus
    confidence: float
    source_event_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class EdgeCreate(BaseModel):
    project_id: uuid.UUID
    source_type: str = Field(..., description="Table name: features, requirements, etc.")
    source_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    edge_type: EdgeType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    description: str | None = None
    metadata: dict = Field(default_factory=dict)


class EdgeOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    edge_type: EdgeType
    weight: float
    description: str | None

    model_config = {"from_attributes": True}


class TraversalRequest(BaseModel):
    start_type: str = Field(..., description="Table name of the starting node")
    start_id: uuid.UUID
    max_depth: int = Field(default=3, ge=1, le=10)
    edge_types: list[EdgeType] | None = None


# ---------------------------------------------------------------------------
# Feature Context
# ---------------------------------------------------------------------------

@router.get("/features/{feature_id}/context", response_model=dict)
async def get_feature_context(
    feature_id: uuid.UUID,
    max_depth: int = Query(default=2, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the full Intelligence Graph context for a feature."""
    result = await graph_service.get_feature_context(db, feature_id, max_depth=max_depth)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Requirements CRUD
# ---------------------------------------------------------------------------

@router.post("/requirements", response_model=RequirementOut, status_code=201)
async def create_requirement(
    payload: RequirementCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new requirement in the Intelligence Graph."""
    req = await graph_service.create_requirement(
        db,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        requirement_type=payload.requirement_type,
        priority=payload.priority,
        confidence=payload.confidence,
        source_event_id=payload.source_event_id,
        metadata=payload.metadata,
    )
    return req


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
async def get_requirement(
    requirement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific requirement by ID."""
    req = await graph_service.get_requirement(db, requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return req


@router.get("/requirements", response_model=list[RequirementOut])
async def list_requirements(
    project_id: uuid.UUID = Query(...),
    status: RequirementStatus | None = None,
    requirement_type: RequirementType | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List requirements for a project, optionally filtered."""
    return await graph_service.list_requirements(
        db, project_id,
        status=status,
        requirement_type=requirement_type,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Decisions CRUD
# ---------------------------------------------------------------------------

@router.post("/decisions", response_model=DecisionOut, status_code=201)
async def create_decision(
    payload: DecisionCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new decision in the Intelligence Graph."""
    decision = await graph_service.create_decision(
        db,
        project_id=payload.project_id,
        title=payload.title,
        rationale=payload.rationale,
        alternatives_considered=payload.alternatives_considered,
        confidence=payload.confidence,
        source_event_id=payload.source_event_id,
        metadata=payload.metadata,
    )
    return decision


@router.get("/decisions/{decision_id}", response_model=DecisionOut)
async def get_decision(
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific decision by ID."""
    decision = await graph_service.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@router.get("/decisions", response_model=list[DecisionOut])
async def list_decisions(
    project_id: uuid.UUID = Query(...),
    status: DecisionStatus | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List decisions for a project, optionally filtered."""
    return await graph_service.list_decisions(
        db, project_id, status=status, limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# Edge Management
# ---------------------------------------------------------------------------

@router.post("/edges", response_model=EdgeOut, status_code=201)
async def create_edge(
    payload: EdgeCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create or update an edge between two graph nodes."""
    edge = await graph_service.create_edge(
        db,
        project_id=payload.project_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        edge_type=payload.edge_type,
        weight=payload.weight,
        description=payload.description,
        metadata=payload.metadata,
    )
    return edge


@router.get("/edges/{node_type}/{node_id}", response_model=list[EdgeOut])
async def get_edges(
    node_type: str,
    node_id: uuid.UUID,
    direction: str = Query(default="both", regex="^(outgoing|incoming|both)$"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all edges connected to a specific node."""
    return await graph_service.get_edges_for_node(
        db, node_type, node_id, direction=direction,
    )


@router.delete("/edges/{edge_id}", status_code=204)
async def delete_edge(
    edge_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a graph edge."""
    deleted = await graph_service.delete_edge(db, edge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Edge not found")


# ---------------------------------------------------------------------------
# Graph Traversal
# ---------------------------------------------------------------------------

@router.post("/traverse", response_model=dict)
async def traverse_graph(
    payload: TraversalRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """BFS traversal from any node — used for impact analysis and conflict detection."""
    return await graph_service.traverse_graph(
        db,
        start_type=payload.start_type,
        start_id=payload.start_id,
        max_depth=payload.max_depth,
        edge_types=payload.edge_types,
    )
