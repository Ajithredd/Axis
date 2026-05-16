"""Tests for the Graph Ingestion Engine — classification and mapping logic.

Tests the rule-based classifier and the GraphIngestionEngine processing
pipeline without requiring a database connection.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.graph import (
    RequirementType, StakeholderRole, EdgeType,
)
from app.services.graph_ingestion import (
    classify_event_content,
    ClassificationResult,
    _calculate_relevance,
    _AUTHORSHIP_EVENT_TYPES,
    _REVIEW_EVENT_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers — create mock Event-like objects without DB
# ---------------------------------------------------------------------------

class MockEvent:
    """Lightweight mock matching the Event interface for classifier testing."""

    def __init__(
        self,
        event_type: str = "issue.created",
        connector_type: str = "gitlab",
        title: str | None = None,
        content: str | None = None,
        actor_name: str | None = "alice",
        actor_email: str | None = "alice@example.com",
    ):
        self.id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.event_type = event_type
        self.connector_type = connector_type
        self.title = title
        self.content = content
        self.actor_name = actor_name
        self.actor_email = actor_email
        self.source_id = "test-123"
        self.source_url = "https://gitlab.com/test"
        self.source_timestamp = datetime.now(timezone.utc)
        self.extra = {}

    @property
    def searchable_text(self) -> str:
        parts = []
        if self.title:
            parts.append(self.title)
        if self.content:
            parts.append(self.content)
        return "\n\n".join(parts)


def _make_event(**kwargs) -> MockEvent:
    """Create a MockEvent for classification testing."""
    return MockEvent(**kwargs)


# ---------------------------------------------------------------------------
# Classification Tests
# ---------------------------------------------------------------------------

class TestClassifyEventContent:
    """Test the rule-based content classifier."""

    def test_extracts_functional_requirements(self):
        event = _make_event(
            content="The system must support SSO authentication for all users. "
                    "It should also handle multi-tenancy."
        )
        result = classify_event_content(event)
        assert len(result.requirements) >= 1
        assert any(
            "SSO" in r.title or "authentication" in r.title
            for r in result.requirements
        )
        assert all(r.confidence > 0 for r in result.requirements)

    def test_extracts_non_functional_requirements(self):
        event = _make_event(
            content="Performance: The API response time must be under 200ms for 95th percentile."
        )
        result = classify_event_content(event)
        assert any(
            r.requirement_type == RequirementType.NON_FUNCTIONAL
            for r in result.requirements
        )

    def test_extracts_constraints(self):
        event = _make_event(
            content="Constraint: We can only use PostgreSQL due to existing infrastructure."
        )
        result = classify_event_content(event)
        assert any(
            r.requirement_type == RequirementType.CONSTRAINT
            for r in result.requirements
        )

    def test_extracts_assumptions(self):
        event = _make_event(
            content="Assuming that all users will have a valid email address on file."
        )
        result = classify_event_content(event)
        assert any(
            r.requirement_type == RequirementType.ASSUMPTION
            for r in result.requirements
        )

    def test_extracts_checklist_items(self):
        event = _make_event(
            content="## Acceptance Criteria\n"
                    "[x] User can log in with Google SSO\n"
                    "[ ] User can reset password via email link"
        )
        result = classify_event_content(event)
        assert len(result.requirements) >= 1

    def test_extracts_decisions(self):
        event = _make_event(
            content="We decided to use FastAPI for the backend framework "
                    "because of its async support and auto-generated docs."
        )
        result = classify_event_content(event)
        assert len(result.decisions) >= 1
        assert any("FastAPI" in d.title for d in result.decisions)

    def test_extracts_decision_with_rationale(self):
        event = _make_event(
            content="We chose PostgreSQL over MongoDB because of ACID compliance."
        )
        result = classify_event_content(event)
        assert len(result.decisions) >= 1

    def test_no_extraction_from_short_content(self):
        event = _make_event(content="OK")
        result = classify_event_content(event)
        assert len(result.requirements) == 0
        assert len(result.decisions) == 0

    def test_empty_content_returns_empty_result(self):
        event = _make_event(content=None, title=None)
        result = classify_event_content(event)
        assert len(result.requirements) == 0
        assert len(result.decisions) == 0

    def test_extracts_feature_keywords(self):
        event = _make_event(
            content="The Authentication feature needs a redesign. "
                    "Related to #42 and the Payment module."
        )
        result = classify_event_content(event)
        assert len(result.feature_keywords) >= 1

    def test_stakeholder_role_from_event_type(self):
        commit_event = _make_event(event_type="commit.pushed")
        result = classify_event_content(commit_event)
        assert result.stakeholder_role == StakeholderRole.DEVELOPER

        issue_event = _make_event(event_type="issue.created")
        result = classify_event_content(issue_event)
        assert result.stakeholder_role == StakeholderRole.PRODUCT_OWNER


# ---------------------------------------------------------------------------
# Event Type Classification Tests
# ---------------------------------------------------------------------------

class TestEventTypeCategories:
    """Verify the event type → edge type mapping is correct."""

    def test_authorship_events(self):
        assert "issue.created" in _AUTHORSHIP_EVENT_TYPES
        assert "commit.pushed" in _AUTHORSHIP_EVENT_TYPES
        assert "merge_request.opened" in _AUTHORSHIP_EVENT_TYPES

    def test_review_events(self):
        assert "merge_request.reviewed" in _REVIEW_EVENT_TYPES
        assert "merge_request.approved" in _REVIEW_EVENT_TYPES
        assert "merge_request.merged" in _REVIEW_EVENT_TYPES


# ---------------------------------------------------------------------------
# Relevance Scoring Tests
# ---------------------------------------------------------------------------

class TestRelevanceScoring:
    """Test the keyword relevance calculation."""

    def test_high_relevance_for_title_mention(self):
        text = "authentication flow redesign is needed for the new SSO feature"
        score = _calculate_relevance(text, "authentication")
        assert score > 0.5

    def test_low_relevance_for_late_mention(self):
        text = "x" * 1000 + " authentication"
        score = _calculate_relevance(text, "authentication")
        assert score < 0.5

    def test_zero_for_empty_inputs(self):
        assert _calculate_relevance("", "test") == 0.0
        assert _calculate_relevance("test", "") == 0.0

    def test_capped_at_one(self):
        text = "auth auth auth auth auth auth auth auth auth auth"
        score = _calculate_relevance(text, "auth")
        assert score <= 1.0

    def test_multiple_occurrences_increase_score(self):
        text_single = "auth is important"
        text_multi = "auth is important, auth handles login, auth controls access"
        score_single = _calculate_relevance(text_single, "auth")
        score_multi = _calculate_relevance(text_multi, "auth")
        assert score_multi >= score_single


# ---------------------------------------------------------------------------
# Classification Result Dataclass Tests
# ---------------------------------------------------------------------------

class TestClassificationResult:
    """Test the ClassificationResult dataclass defaults."""

    def test_default_empty_lists(self):
        result = ClassificationResult()
        assert result.requirements == []
        assert result.decisions == []
        assert result.feature_keywords == []
        assert result.stakeholder_role == StakeholderRole.DEVELOPER
