"""
Base connector — abstract interface for all integrations.

To add a new integration (e.g., Slack, Confluence, Email):
  1. Create a folder: app/connectors/slack/
  2. Subclass BaseConnector in app/connectors/slack/connector.py
  3. Implement all abstract methods
  4. It auto-registers via ConnectorRegistry.discover()

That's it. No other files need to change.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedEvent:
    """
    The universal event format that ALL connectors must produce.

    Whether it comes from GitLab, Slack, Confluence, or email —
    every piece of content gets normalized into this shape before
    storage and processing.
    """
    # Which connector produced this (e.g., "gitlab", "slack")
    connector_type: str

    # Unique ID in the source system
    source_id: str

    # URL back to the original item
    source_url: str | None

    # Normalized event type (e.g., "issue.created", "message.sent")
    event_type: str

    # Content
    title: str | None
    content: str | None

    # Who performed this action
    actor_name: str | None
    actor_email: str | None

    # When it happened in the source system
    source_timestamp: datetime

    # Connector-specific extra data (labels, channels, etc.)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorInfo:
    """Metadata about a connector for the UI and registry."""
    type: str              # e.g., "gitlab"
    display_name: str      # e.g., "GitLab"
    description: str       # e.g., "Connect to GitLab projects..."
    icon: str              # e.g., "gitlab" (for frontend icon lookup)
    auth_type: str         # "oauth2" | "api_key" | "webhook_only"
    config_schema: dict    # JSON Schema describing required config fields


class BaseConnector(ABC):
    """
    Abstract base class for all Axis connectors.

    Every integration (GitLab, Slack, Confluence, Email, etc.)
    must implement this interface.
    """

    @abstractmethod
    def info(self) -> ConnectorInfo:
        """Return metadata about this connector."""
        ...

    @abstractmethod
    async def validate_config(self, config: dict) -> bool:
        """
        Validate that the provided config is valid.
        e.g., check that the GitLab project exists and is accessible.
        """
        ...

    @abstractmethod
    async def sync_all(
        self,
        config: dict,
        access_token: str,
        since: datetime | None = None,
    ) -> list[NormalizedEvent]:
        """
        Full sync: fetch all relevant content from the source.

        If `since` is provided, only fetch events after that timestamp
        (incremental sync).

        Returns a list of NormalizedEvents to be stored and embedded.
        """
        ...

    @abstractmethod
    async def handle_webhook(
        self,
        payload: dict,
        headers: dict,
        webhook_secret: str | None = None,
    ) -> list[NormalizedEvent] | None:
        """
        Process an incoming webhook from the source system.

        Returns NormalizedEvents if the webhook contains relevant content,
        or None if it should be ignored.
        """
        ...

    @abstractmethod
    def get_event_types(self) -> list[str]:
        """
        Return all event types this connector can produce.
        e.g., ["issue.created", "issue.updated", "merge_request.opened", ...]
        """
        ...

    async def get_oauth_url(self, state: str, redirect_uri: str) -> str | None:
        """
        Return the OAuth authorization URL for this connector.
        Override if the connector uses OAuth2.
        Returns None if the connector doesn't use OAuth.
        """
        return None

    async def exchange_oauth_code(
        self, code: str, redirect_uri: str
    ) -> dict | None:
        """
        Exchange an OAuth authorization code for tokens.
        Override if the connector uses OAuth2.
        Returns {"access_token": ..., "refresh_token": ..., ...} or None.
        """
        return None

    async def setup_webhook(
        self,
        config: dict,
        access_token: str,
        webhook_url: str,
        webhook_secret: str,
    ) -> bool:
        """
        Register a webhook in the source system.
        Override if the connector supports webhooks.
        Returns True if successful.
        """
        return False
