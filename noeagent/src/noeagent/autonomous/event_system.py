"""Event system for autonomous agents (RFC-1007).

Provides a unified event model for reactive behavior in autonomous systems.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


class AutonomousEvent(BaseModel):
    """Generic event for autonomous system (RFC-1007 Section 6).

    Events provide the reactive layer that enables the agent to detect and
    respond to changes in the environment.

    Event sources emit events to the EventBus, which are then processed by
    EventProcessors using trigger rules.
    """

    id: str = Field(default_factory=uuid7str, description="Unique event identifier")
    type: str = Field(description="Event type (e.g., 'timer', 'filesystem.change', 'github.issue.created')")
    source: str = Field(description="Event origin (e.g., 'timer_service', 'github_webhook')")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Event timestamp",
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
