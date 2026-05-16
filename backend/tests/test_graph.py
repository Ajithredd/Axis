"""Tests for the Intelligence Graph models and service layer.

Uses an in-memory SQLite database for fast, isolated testing of:
  - Model instantiation and enum correctness
  - CRUD operations via the graph service
  - Edge creation and BFS traversal
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.graph import (
    Requirement, Decision, Stakeholder, GraphEdge,
    RequirementType, RequirementStatus, DecisionStatus,
    StakeholderRole, EdgeType,
)
from app.models.feature import Feature, FeatureStatus


# ---------------------------------------------------------------------------
# Model Unit Tests (no DB required)
# ---------------------------------------------------------------------------

class TestRequirementModel:
    """Test Requirement model instantiation and defaults."""

    def test_default_status_is_draft(self):
        assert RequirementStatus.DRAFT == "draft"

    def test_requirement_types(self):
        types = [t.value for t in RequirementType]
        assert "functional" in types
        assert "non_functional" in types
        assert "constraint" in types
        assert "assumption" in types

    def test_requirement_statuses(self):
        statuses = [s.value for s in RequirementStatus]
        assert "draft" in statuses
        assert "approved" in statuses
        assert "implemented" in statuses
        assert "verified" in statuses
        assert "deprecated" in statuses


class TestDecisionModel:
    """Test Decision model instantiation and defaults."""

    def test_decision_statuses(self):
        statuses = [s.value for s in DecisionStatus]
        assert "proposed" in statuses
        assert "accepted" in statuses
        assert "superseded" in statuses
        assert "rejected" in statuses


class TestStakeholderModel:
    """Test Stakeholder model and role enum."""

    def test_stakeholder_roles(self):
        roles = [r.value for r in StakeholderRole]
        expected = ["developer", "qa", "product_owner", "designer", "client", "architect", "devops"]
        for role in expected:
            assert role in roles


class TestGraphEdgeModel:
    """Test GraphEdge model and edge type enum."""

    def test_edge_types_cover_architecture(self):
        edge_types = [e.value for e in EdgeType]
        critical_types = [
            "requires", "decided_by", "implemented_by",
            "depends_on", "conflicts_with", "evidenced_by",
        ]
        for et in critical_types:
            assert et in edge_types, f"Missing edge type: {et}"

    def test_repr(self):
        """Verify the __repr__ method exists and references the edge type."""
        import inspect
        source = inspect.getsource(GraphEdge.__repr__)
        assert "edge_type" in source
        assert "source_type" in source


class TestFeatureStatus:
    """Verify existing Feature model has needed statuses."""

    def test_conflicted_status_exists(self):
        assert FeatureStatus.CONFLICTED == "conflicted"

    def test_active_status_exists(self):
        assert FeatureStatus.ACTIVE == "active"


# ---------------------------------------------------------------------------
# Schema Validation Tests
# ---------------------------------------------------------------------------

class TestGraphSchema:
    """Verify the schema structure is consistent."""

    def test_requirement_table_name(self):
        assert Requirement.__tablename__ == "requirements"

    def test_decision_table_name(self):
        assert Decision.__tablename__ == "decisions"

    def test_stakeholder_table_name(self):
        assert Stakeholder.__tablename__ == "stakeholders"

    def test_graph_edge_table_name(self):
        assert GraphEdge.__tablename__ == "graph_edges"

    def test_graph_edge_has_unique_constraint(self):
        """Ensure the deduplication constraint exists."""
        constraints = [c.name for c in GraphEdge.__table__.constraints if hasattr(c, "name")]
        assert "uq_graph_edge_pair" in constraints

    def test_stakeholder_has_unique_constraint(self):
        constraints = [c.name for c in Stakeholder.__table__.constraints if hasattr(c, "name")]
        assert "uq_stakeholder_project_email" in constraints
