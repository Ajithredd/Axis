"""Graph Ingestion Engine — automatically maps incoming events to the Intelligence Graph.

This module is the bridge between the raw event ingestion pipeline and the
Feature Intelligence Graph. When a new event is stored, this engine:

  1. Resolves the actor → Stakeholder node (deduplication by email)
  2. Classifies the event content using an LLM to detect:
     - Requirements (functional, constraints, assumptions)
     - Decisions (architecture, tool choices, process changes)
  3. Links the event to existing Features via FeatureLink
  4. Creates typed edges in the graph (REQUIRES, DECIDED_BY, AUTHORED, etc.)
  5. Maintains graph consistency (no orphaned nodes)

Usage:
    from app.services.graph_ingestion import GraphIngestionEngine

    engine = GraphIngestionEngine(db)
    stats = await engine.process_event(event)
"""

import uuid
import re
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.feature import Feature, FeatureLink, FeatureStatus
from app.models.graph import (
    Requirement, Decision, Stakeholder, GraphEdge,
    RequirementType, RequirementStatus, DecisionStatus,
    StakeholderRole, EdgeType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification result types
# ---------------------------------------------------------------------------

@dataclass
class ExtractedRequirement:
    """A requirement extracted from event content."""
    title: str
    description: str | None = None
    requirement_type: RequirementType = RequirementType.FUNCTIONAL
    confidence: float = 0.0


@dataclass
class ExtractedDecision:
    """A decision extracted from event content."""
    title: str
    rationale: str | None = None
    confidence: float = 0.0


@dataclass
class ClassificationResult:
    """Result of classifying an event's content."""
    requirements: list[ExtractedRequirement] = field(default_factory=list)
    decisions: list[ExtractedDecision] = field(default_factory=list)
    feature_keywords: list[str] = field(default_factory=list)
    stakeholder_role: StakeholderRole = StakeholderRole.DEVELOPER


# ---------------------------------------------------------------------------
# Event → Content classifier (rule-based with LLM extension point)
# ---------------------------------------------------------------------------

# Patterns that suggest requirements
_REQUIREMENT_PATTERNS = [
    (r"(?:must|shall|should|needs? to)\s+(.+?)(?:\.|$)", RequirementType.FUNCTIONAL),
    (r"(?:the system|it|we)\s+(?:must|shall|should)\s+(.+?)(?:\.|$)", RequirementType.FUNCTIONAL),
    (r"(?:non-functional|performance|security|scalability)[\s:]+(.+?)(?:\.|$)", RequirementType.NON_FUNCTIONAL),
    (r"(?:constraint|limitation|restriction)[\s:]+(.+?)(?:\.|$)", RequirementType.CONSTRAINT),
    (r"(?:assum(?:e|ing|ption))[\s:]+(.+?)(?:\.|$)", RequirementType.ASSUMPTION),
    (r"\[x?\]\s+(.+?)$", RequirementType.FUNCTIONAL),  # Checklist items
]

# Patterns that suggest decisions
_DECISION_PATTERNS = [
    r"(?:decided|decision|we(?:'ll| will) (?:use|go with|choose))\s+(.+?)(?:\.|$)",
    r"(?:chose|chosen|selected|picking|went with)\s+(.+?)(?:\.|$)",
    r"(?:instead of|rather than|over)\s+(.+?)(?:,|\.|\s+because)",
    r"(?:ADR|architecture decision)[\s:#]+(.+?)(?:\.|$)",
]

# Event types that indicate authorship vs review
_AUTHORSHIP_EVENT_TYPES = {
    "issue.created", "issue.commented", "merge_request.opened",
    "commit.pushed", "message.sent", "page.created", "email.sent",
}
_REVIEW_EVENT_TYPES = {
    "merge_request.reviewed", "merge_request.approved",
    "issue.closed", "merge_request.merged",
}

# Map connector types / event types to likely stakeholder roles
_ROLE_HINTS: dict[str, StakeholderRole] = {
    "commit.pushed": StakeholderRole.DEVELOPER,
    "merge_request.opened": StakeholderRole.DEVELOPER,
    "merge_request.reviewed": StakeholderRole.DEVELOPER,
    "issue.created": StakeholderRole.PRODUCT_OWNER,
    "pipeline.failed": StakeholderRole.DEVOPS,
    "pipeline.succeeded": StakeholderRole.DEVOPS,
}


def classify_event_content(event: Event) -> ClassificationResult:
    """
    Classify an event's content using rule-based heuristics.

    This is the fast-path classifier that runs synchronously.
    For higher accuracy, the LLM classifier (Enabler #11) will
    augment these results asynchronously.
    """
    result = ClassificationResult()
    text = event.searchable_text or ""
    text_lower = text.lower()

    # --- Extract requirements ---
    for pattern, req_type in _REQUIREMENT_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            title = match.group(1).strip()
            if len(title) > 10:  # Skip very short matches (noise)
                result.requirements.append(ExtractedRequirement(
                    title=title[:500],
                    description=f"Extracted from: {event.event_type} — {event.title or 'untitled'}",
                    requirement_type=req_type,
                    confidence=0.5,  # Rule-based = medium confidence
                ))

    # --- Extract decisions ---
    for pattern in _DECISION_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            title = match.group(1).strip()
            if len(title) > 10:
                # Try to find rationale (text after "because")
                rationale = None
                because_match = re.search(
                    r"because\s+(.+?)(?:\.|$)", text[match.end():],
                    re.IGNORECASE
                )
                if because_match:
                    rationale = because_match.group(1).strip()

                result.decisions.append(ExtractedDecision(
                    title=title[:500],
                    rationale=rationale,
                    confidence=0.5,
                ))

    # --- Extract feature keywords ---
    # Look for references to features, components, or modules
    keyword_patterns = [
        r"(?:feature|component|module|service|system)[\s:]+[\"']?([A-Z][a-zA-Z\s]+)[\"']?",
        r"#(\d+)",  # Issue references
    ]
    for pattern in keyword_patterns:
        for match in re.finditer(pattern, text):
            result.feature_keywords.append(match.group(1).strip())

    # --- Determine stakeholder role ---
    result.stakeholder_role = _ROLE_HINTS.get(
        event.event_type, StakeholderRole.DEVELOPER
    )

    return result


# ---------------------------------------------------------------------------
# Graph Ingestion Engine
# ---------------------------------------------------------------------------

class GraphIngestionEngine:
    """
    Processes ingested events and weaves them into the Intelligence Graph.

    This engine is designed to be called after an event is stored in the
    database. It enriches the graph with:
      - Stakeholder nodes (from actor data)
      - Requirement nodes (from content classification)
      - Decision nodes (from content classification)
      - Typed edges connecting everything
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_event(self, event: Event) -> dict[str, Any]:
        """
        Process a single event and update the Intelligence Graph.

        Returns stats about what was created/linked.
        """
        stats = {
            "stakeholders_resolved": 0,
            "requirements_extracted": 0,
            "decisions_extracted": 0,
            "edges_created": 0,
            "features_linked": 0,
        }

        # 1. Resolve stakeholder
        stakeholder = await self._resolve_stakeholder(event)
        if stakeholder:
            stats["stakeholders_resolved"] = 1

        # 2. Classify event content
        classification = classify_event_content(event)

        # 3. Extract and store requirements
        for ext_req in classification.requirements:
            req = await self._create_requirement(event, ext_req)
            stats["requirements_extracted"] += 1

            # Link requirement to event via evidence edge
            await self._create_edge(
                event.project_id,
                "requirements", req.id,
                "events", event.id,
                EdgeType.EVIDENCED_BY,
                weight=ext_req.confidence,
            )
            stats["edges_created"] += 1

            # Link stakeholder as author of requirement
            if stakeholder:
                await self._create_edge(
                    event.project_id,
                    "stakeholders", stakeholder.id,
                    "requirements", req.id,
                    EdgeType.AUTHORED,
                )
                stats["edges_created"] += 1

        # 4. Extract and store decisions
        for ext_dec in classification.decisions:
            dec = await self._create_decision(event, ext_dec)
            stats["decisions_extracted"] += 1

            # Link decision to event via evidence edge
            await self._create_edge(
                event.project_id,
                "decisions", dec.id,
                "events", event.id,
                EdgeType.EVIDENCED_BY,
                weight=ext_dec.confidence,
            )
            stats["edges_created"] += 1

            # Link stakeholder as author of decision
            if stakeholder:
                await self._create_edge(
                    event.project_id,
                    "stakeholders", stakeholder.id,
                    "decisions", dec.id,
                    EdgeType.AUTHORED,
                )
                stats["edges_created"] += 1

        # 5. Link event to matching features
        features_linked = await self._link_to_features(event, classification)
        stats["features_linked"] = features_linked

        # 6. Link stakeholder to event
        if stakeholder:
            edge_type = (
                EdgeType.AUTHORED
                if event.event_type in _AUTHORSHIP_EVENT_TYPES
                else EdgeType.REVIEWED
                if event.event_type in _REVIEW_EVENT_TYPES
                else EdgeType.EVIDENCED_BY
            )
            await self._create_edge(
                event.project_id,
                "stakeholders", stakeholder.id,
                "events", event.id,
                edge_type,
            )
            stats["edges_created"] += 1

        return stats

    async def process_batch(self, events: list[Event]) -> dict[str, Any]:
        """Process multiple events and return aggregate stats."""
        totals: dict[str, int] = {}
        for event in events:
            stats = await self.process_event(event)
            for key, val in stats.items():
                totals[key] = totals.get(key, 0) + val
        return totals

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    async def _resolve_stakeholder(self, event: Event) -> Stakeholder | None:
        """Resolve or create a Stakeholder node from event actor data."""
        if not event.actor_name and not event.actor_email:
            return None

        # Try to find existing by email first
        if event.actor_email:
            stmt = select(Stakeholder).where(
                Stakeholder.project_id == event.project_id,
                Stakeholder.email == event.actor_email,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        # Try by display name
        if event.actor_name:
            stmt = select(Stakeholder).where(
                Stakeholder.project_id == event.project_id,
                Stakeholder.display_name == event.actor_name,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                # Update email if we have one now
                if event.actor_email and not existing.email:
                    existing.email = event.actor_email
                    await self.db.flush()
                return existing

        # Create new stakeholder
        role = _ROLE_HINTS.get(event.event_type, StakeholderRole.DEVELOPER)
        external_ids = {}
        if event.connector_type == "gitlab" and event.actor_name:
            external_ids["gitlab_username"] = event.actor_name

        stakeholder = Stakeholder(
            project_id=event.project_id,
            display_name=event.actor_name or event.actor_email or "Unknown",
            email=event.actor_email,
            role=role,
            external_ids=external_ids,
        )
        self.db.add(stakeholder)
        await self.db.flush()
        return stakeholder

    async def _create_requirement(
        self, event: Event, extracted: ExtractedRequirement
    ) -> Requirement:
        """Create or update a Requirement node from an extraction result and sync to Qdrant."""
        from datetime import datetime
        from app.services.vector_sync import sync_node_to_vector_store
        
        # Check if a requirement with identical title+project_id or source_event_id already exists
        stmt = select(Requirement).where(
            (Requirement.project_id == event.project_id) &
            (
                (Requirement.source_event_id == event.id) |
                (Requirement.title == extracted.title)
            )
        )
        res = await self.db.execute(stmt)
        req = res.scalar_one_or_none()

        if req:
            req.description = extracted.description
            req.requirement_type = extracted.requirement_type
            req.confidence = extracted.confidence
            req.extra_metadata = {
                "extracted_from": event.event_type,
                "source_url": event.source_url,
                "updated_at": datetime.utcnow().isoformat()
            }
            logger.info(f"Deduplicated: updating existing Requirement node {req.id} (Title: {req.title})")
        else:
            req = Requirement(
                project_id=event.project_id,
                title=extracted.title,
                description=extracted.description,
                requirement_type=extracted.requirement_type,
                status=RequirementStatus.DRAFT,
                confidence=extracted.confidence,
                source_event_id=event.id,
                extra_metadata={
                    "extracted_from": event.event_type,
                    "source_url": event.source_url,
                },
            )
            self.db.add(req)
            logger.info(f"Creating new Requirement node (Title: {req.title})")
            
        await self.db.flush()

        # Synchronize to Qdrant vector store
        try:
            await sync_node_to_vector_store(
                collection_name="requirements",
                node_id=req.id,
                project_id=req.project_id,
                node_type="requirements",
                content=f"{req.title}: {req.description or ''}",
                metadata={"title": req.title}
            )
        except Exception as vec_err:
            logger.error(f"Failed to sync requirement {req.id} to vector store: {vec_err}")

        return req

    async def _create_decision(
        self, event: Event, extracted: ExtractedDecision
    ) -> Decision:
        """Create or update a Decision node from an extraction result and sync to Qdrant."""
        from datetime import datetime
        from app.services.vector_sync import sync_node_to_vector_store

        # Check if a decision with identical title+project_id or source_event_id already exists
        stmt = select(Decision).where(
            (Decision.project_id == event.project_id) &
            (
                (Decision.source_event_id == event.id) |
                (Decision.title == extracted.title)
            )
        )
        res = await self.db.execute(stmt)
        dec = res.scalar_one_or_none()

        if dec:
            dec.rationale = extracted.rationale
            dec.confidence = extracted.confidence
            dec.extra_metadata = {
                "extracted_from": event.event_type,
                "source_url": event.source_url,
                "updated_at": datetime.utcnow().isoformat()
            }
            logger.info(f"Deduplicated: updating existing Decision node {dec.id} (Title: {dec.title})")
        else:
            dec = Decision(
                project_id=event.project_id,
                title=extracted.title,
                rationale=extracted.rationale,
                status=DecisionStatus.PROPOSED,
                confidence=extracted.confidence,
                source_event_id=event.id,
                extra_metadata={
                    "extracted_from": event.event_type,
                    "source_url": event.source_url,
                },
            )
            self.db.add(dec)
            logger.info(f"Creating new Decision node (Title: {dec.title})")

        await self.db.flush()

        # Synchronize to Qdrant vector store
        try:
            await sync_node_to_vector_store(
                collection_name="decisions",
                node_id=dec.id,
                project_id=dec.project_id,
                node_type="decisions",
                content=f"{dec.title}: {dec.rationale or ''}",
                metadata={"title": dec.title}
            )
        except Exception as vec_err:
            logger.error(f"Failed to sync decision {dec.id} to vector store: {vec_err}")

        return dec

    async def _create_edge(
        self,
        project_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        edge_type: EdgeType,
        weight: float = 1.0,
        description: str | None = None,
    ) -> GraphEdge:
        """Create or update a graph edge (upsert semantics)."""
        from app.services.graph import create_edge
        return await create_edge(
            self.db,
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            description=description,
        )

    async def _link_to_features(
        self, event: Event, classification: ClassificationResult
    ) -> int:
        """
        Link an event to relevant Features using keyword matching.

        Returns the number of features linked.
        """
        linked_count = 0
        text = (event.searchable_text or "").lower()
        if not text:
            return 0

        # Get all features for this project
        stmt = select(Feature).where(Feature.project_id == event.project_id)
        result = await self.db.execute(stmt)
        features = result.scalars().all()

        for feature in features:
            feature_name_lower = feature.name.lower()

            # Check if the feature name appears in the event content
            if feature_name_lower in text:
                relevance = _calculate_relevance(text, feature_name_lower)

                # Create FeatureLink
                existing_link = await self.db.execute(
                    select(FeatureLink).where(
                        FeatureLink.feature_id == feature.id,
                        FeatureLink.event_id == event.id,
                    )
                )
                if not existing_link.scalar_one_or_none():
                    link = FeatureLink(
                        feature_id=feature.id,
                        event_id=event.id,
                        relevance=relevance,
                    )
                    self.db.add(link)

                # Also create a graph edge
                await self._create_edge(
                    event.project_id,
                    "features", feature.id,
                    "events", event.id,
                    EdgeType.IMPLEMENTED_BY,
                    weight=relevance,
                )
                linked_count += 1

        await self.db.flush()
        return linked_count


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _calculate_relevance(text: str, keyword: str) -> float:
    """
    Calculate relevance score (0.0–1.0) based on keyword frequency
    and position in the text.
    """
    if not keyword or not text:
        return 0.0

    count = text.count(keyword)
    # Frequency component (logarithmic scaling)
    freq_score = min(count / 5.0, 1.0)

    # Position component (earlier mentions = more relevant)
    first_pos = text.find(keyword)
    pos_score = max(0.0, 1.0 - (first_pos / len(text)))

    # Title mention bonus
    title_bonus = 0.2 if keyword in text[:200] else 0.0

    return min(1.0, (freq_score * 0.4 + pos_score * 0.4 + title_bonus))
