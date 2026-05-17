"""Intelligence Graph service — CRUD and traversal logic for the Feature Intelligence Graph.

This service provides:
  1. Node management — create/read/update for Requirements, Decisions, Stakeholders.
  2. Edge management — link any two graph entities with a typed, weighted edge.
  3. Graph traversal — BFS-based impact analysis, conflict detection, and context retrieval.
"""

import uuid
from collections import deque
from typing import Any

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import (
    Requirement, Decision, Stakeholder, GraphEdge,
    RequirementType, RequirementStatus, DecisionStatus,
    StakeholderRole, EdgeType,
)
from app.models.feature import Feature
from app.models.event import Event


# ---------------------------------------------------------------------------
# Table-name ↔ Model registry (for generic graph operations)
# ---------------------------------------------------------------------------
_NODE_MODELS: dict[str, type] = {
    "features": Feature,
    "requirements": Requirement,
    "decisions": Decision,
    "stakeholders": Stakeholder,
    "events": Event,
}


# ===================================================================
# Requirement CRUD
# ===================================================================

async def create_requirement(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str | None = None,
    requirement_type: RequirementType = RequirementType.FUNCTIONAL,
    priority: int = 0,
    confidence: float = 0.0,
    source_event_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> Requirement:
    """Create a new requirement node in the graph."""
    req = Requirement(
        project_id=project_id,
        title=title,
        description=description,
        requirement_type=requirement_type,
        priority=priority,
        confidence=confidence,
        source_event_id=source_event_id,
        extra_metadata=metadata or {},
    )
    db.add(req)
    await db.flush()
    return req


async def get_requirement(db: AsyncSession, requirement_id: uuid.UUID) -> Requirement | None:
    return await db.get(Requirement, requirement_id)


async def list_requirements(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    status: RequirementStatus | None = None,
    requirement_type: RequirementType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Requirement]:
    stmt = select(Requirement).where(Requirement.project_id == project_id)
    if status:
        stmt = stmt.where(Requirement.status == status)
    if requirement_type:
        stmt = stmt.where(Requirement.requirement_type == requirement_type)
    stmt = stmt.order_by(Requirement.priority.desc(), Requirement.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ===================================================================
# Decision CRUD
# ===================================================================

async def create_decision(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    title: str,
    rationale: str | None = None,
    alternatives_considered: str | None = None,
    confidence: float = 0.0,
    source_event_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> Decision:
    """Create a new decision node in the graph."""
    decision = Decision(
        project_id=project_id,
        title=title,
        rationale=rationale,
        alternatives_considered=alternatives_considered,
        confidence=confidence,
        source_event_id=source_event_id,
        extra_metadata=metadata or {},
    )
    db.add(decision)
    await db.flush()
    return decision


async def get_decision(db: AsyncSession, decision_id: uuid.UUID) -> Decision | None:
    return await db.get(Decision, decision_id)


async def list_decisions(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    status: DecisionStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Decision]:
    stmt = select(Decision).where(Decision.project_id == project_id)
    if status:
        stmt = stmt.where(Decision.status == status)
    stmt = stmt.order_by(Decision.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ===================================================================
# Stakeholder CRUD
# ===================================================================

async def create_stakeholder(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    display_name: str,
    email: str | None = None,
    role: StakeholderRole = StakeholderRole.DEVELOPER,
    external_ids: dict | None = None,
) -> Stakeholder:
    """Create a new stakeholder node (or return existing if email matches)."""
    if email:
        stmt = select(Stakeholder).where(
            and_(
                Stakeholder.project_id == project_id,
                Stakeholder.email == email,
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    stakeholder = Stakeholder(
        project_id=project_id,
        display_name=display_name,
        email=email,
        role=role,
        external_ids=external_ids or {},
    )
    db.add(stakeholder)
    await db.flush()
    return stakeholder


async def get_stakeholder(db: AsyncSession, stakeholder_id: uuid.UUID) -> Stakeholder | None:
    return await db.get(Stakeholder, stakeholder_id)


# ===================================================================
# Graph Edge Management
# ===================================================================

async def create_edge(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    edge_type: EdgeType,
    weight: float = 1.0,
    description: str | None = None,
    metadata: dict | None = None,
) -> GraphEdge:
    """Create a directed edge between two graph nodes. Upserts on duplicate."""
    # Check for existing edge
    stmt = select(GraphEdge).where(
        and_(
            GraphEdge.source_type == source_type,
            GraphEdge.source_id == source_id,
            GraphEdge.target_type == target_type,
            GraphEdge.target_id == target_id,
            GraphEdge.edge_type == edge_type,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.weight = weight
        if description:
            existing.description = description
        await db.flush()
        return existing

    edge = GraphEdge(
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        edge_type=edge_type,
        weight=weight,
        description=description,
        extra_metadata=metadata or {},
    )
    db.add(edge)
    await db.flush()
    return edge


async def get_edges_for_node(
    db: AsyncSession,
    node_type: str,
    node_id: uuid.UUID,
    *,
    direction: str = "both",  # "outgoing", "incoming", "both"
    edge_types: list[EdgeType] | None = None,
) -> list[GraphEdge]:
    """Get all edges connected to a specific node."""
    conditions = []
    if direction in ("outgoing", "both"):
        cond = and_(GraphEdge.source_type == node_type, GraphEdge.source_id == node_id)
        conditions.append(cond)
    if direction in ("incoming", "both"):
        cond = and_(GraphEdge.target_type == node_type, GraphEdge.target_id == node_id)
        conditions.append(cond)

    stmt = select(GraphEdge).where(or_(*conditions))
    if edge_types:
        stmt = stmt.where(GraphEdge.edge_type.in_(edge_types))
    stmt = stmt.order_by(GraphEdge.weight.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_edge(db: AsyncSession, edge_id: uuid.UUID) -> bool:
    """Delete a graph edge by ID."""
    edge = await db.get(GraphEdge, edge_id)
    if edge:
        await db.delete(edge)
        await db.flush()
        return True
    return False


# ===================================================================
# Graph Traversal — BFS for impact analysis
# ===================================================================

async def traverse_graph(
    db: AsyncSession,
    start_type: str,
    start_id: uuid.UUID,
    *,
    max_depth: int = 3,
    edge_types: list[EdgeType] | None = None,
) -> dict[str, Any]:
    """
    Breadth-first traversal from a starting node.

    Returns a dict with:
      - nodes: list of {type, id, depth} for all reachable nodes
      - edges: list of edge dicts connecting them
      - depth_map: {node_key: depth} for shortest-path depth
    """
    visited: set[str] = set()
    queue: deque[tuple[str, uuid.UUID, int]] = deque()
    queue.append((start_type, start_id, 0))

    start_key = f"{start_type}:{start_id}"
    visited.add(start_key)

    nodes: list[dict] = [{"type": start_type, "id": str(start_id), "depth": 0}]
    edges_out: list[dict] = []
    depth_map: dict[str, int] = {start_key: 0}

    while queue:
        node_type, node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        connected_edges = await get_edges_for_node(
            db, node_type, node_id, edge_types=edge_types
        )

        for edge in connected_edges:
            # Determine the "other" node
            if edge.source_type == node_type and edge.source_id == node_id:
                neighbor_type = edge.target_type
                neighbor_id = edge.target_id
            else:
                neighbor_type = edge.source_type
                neighbor_id = edge.source_id

            neighbor_key = f"{neighbor_type}:{neighbor_id}"

            edges_out.append({
                "id": str(edge.id),
                "source_type": edge.source_type,
                "source_id": str(edge.source_id),
                "target_type": edge.target_type,
                "target_id": str(edge.target_id),
                "edge_type": edge.edge_type.value,
                "weight": edge.weight,
            })

            if neighbor_key not in visited:
                visited.add(neighbor_key)
                new_depth = depth + 1
                depth_map[neighbor_key] = new_depth
                nodes.append({
                    "type": neighbor_type,
                    "id": str(neighbor_id),
                    "depth": new_depth,
                })
                queue.append((neighbor_type, neighbor_id, new_depth))

    return {
        "nodes": nodes,
        "edges": edges_out,
        "depth_map": depth_map,
        "total_nodes": len(nodes),
        "total_edges": len(edges_out),
    }


async def get_feature_context(
    db: AsyncSession,
    feature_id: uuid.UUID,
    *,
    max_depth: int = 2,
) -> dict[str, Any]:
    """
    Get the full Intelligence Graph context for a Feature.

    Returns the feature details + all connected requirements, decisions,
    stakeholders, and events within the specified traversal depth.
    """
    feature = await db.get(Feature, feature_id)
    if not feature:
        return {"error": "Feature not found"}

    graph = await traverse_graph(
        db, "features", feature_id, max_depth=max_depth
    )

    # Resolve actual node data for each discovered node
    resolved_nodes: list[dict] = []
    for node_info in graph["nodes"]:
        model_cls = _NODE_MODELS.get(node_info["type"])
        if model_cls:
            obj = await db.get(model_cls, uuid.UUID(node_info["id"]))
            if obj:
                resolved_nodes.append({
                    "type": node_info["type"],
                    "id": node_info["id"],
                    "depth": node_info["depth"],
                    "title": getattr(obj, "title", None) or getattr(obj, "name", None) or getattr(obj, "display_name", None),
                    "status": getattr(obj, "status", None),
                })

    return {
        "feature": {
            "id": str(feature.id),
            "name": feature.name,
            "description": feature.description,
            "status": feature.status.value,
            "confidence": feature.confidence,
        },
        "graph": {
            "nodes": resolved_nodes,
            "edges": graph["edges"],
            "total_nodes": graph["total_nodes"],
            "total_edges": graph["total_edges"],
        },
    }


async def get_node_with_edges(db: AsyncSession, node_id: uuid.UUID) -> dict[str, Any]:
    """Get a node's incoming and outgoing edges by its ID."""
    stmt_in = select(GraphEdge).where(GraphEdge.target_id == node_id)
    res_in = await db.execute(stmt_in)
    incoming = list(res_in.scalars().all())

    stmt_out = select(GraphEdge).where(GraphEdge.source_id == node_id)
    res_out = await db.execute(stmt_out)
    outgoing = list(res_out.scalars().all())

    return {
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
    }

