"""Repository models for Voyager."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


class Repository(BaseModel):
    """A Git repository managed by Voyager."""

    id: str = Field(default_factory=uuid7str)
    name: str
    url: str  # Git remote URL
    local_path: str
    default_branch: str = "main"
    last_synced: datetime | None = None
    is_cloned: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class RepositoryCreate(BaseModel):
    """Request body for adding a repository."""

    url: str
    name: str | None = None  # Derived from URL if not provided
    default_branch: str = "main"
