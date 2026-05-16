"""Pydantic models for Vector DB (Qdrant) schemas."""

import uuid
from typing import Any
from pydantic import BaseModel, Field

class VectorPayload(BaseModel):
    """Base payload for all nodes stored in Qdrant."""
    project_id: str
    node_type: str = Field(..., description="E.g., 'requirement', 'decision', 'event'")
    node_id: str
    content: str = Field(..., description="The raw text that was embedded")
    metadata: dict[str, Any] = Field(default_factory=dict)

class SearchResult(BaseModel):
    """Result from a vector search query."""
    id: str | int
    score: float
    payload: VectorPayload
