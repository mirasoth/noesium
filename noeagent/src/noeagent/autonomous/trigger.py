"""Trigger rules for converting events to goals (RFC-1007 Section 8).

Trigger rules define conditions under which events generate goals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .event_system import AutonomousEvent


class Trigger(BaseModel):
    """Trigger rule that converts events to goals (RFC-1007 Section 8).

    Triggers define:
    - Event type to match
    - Optional condition function for fine-grained filtering
    - Goal template for creating goals when triggered
    - Priority for created goals

    Example:
        trigger = Trigger(
            id="github-issue-trigger",
            event_type="github.issue.created",
            goal_template="Review new GitHub issue {issue_id} in {repo}",
            priority=70,
        )
    """

    id: str = Field(description="Unique trigger identifier")
    event_type: str = Field(description="Event type to match (e.g., 'github.issue.created')")
    condition: Callable[[AutonomousEvent], bool] | None = Field(
        default=None,
        description="Optional condition function for filtering events",
        exclude=True,  # Exclude from serialization
    )
    goal_template: str = Field(
        description="Goal description template. Use {field} to substitute from event.payload",
    )
    priority: int = Field(ge=0, le=100, default=50, description="Priority for created goals")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def evaluate(self, event: AutonomousEvent) -> bool:
        """Check if trigger fires for this event.

        Args:
            event: Event to evaluate

        Returns:
            True if trigger should fire
        """
        # Match event type
        if event.type != self.event_type:
            return False

        # Evaluate condition if present
        if self.condition is None:
            return True

        try:
            return self.condition(event)
        except Exception:
            # If condition evaluation fails, don't fire
            return False

    def create_goal_description(self, event: AutonomousEvent) -> str:
        """Generate goal description from template.

        Substitutes {field} placeholders with values from event.payload.

        Args:
            event: Event that triggered this rule

        Returns:
            Goal description string
        """
        try:
            return self.goal_template.format(**event.payload)
        except (KeyError, ValueError):
            # If substitution fails, return template as-is
            return self.goal_template


class TriggerRule(BaseModel):
    """Simplified trigger rule without callable condition.

    Used for serialization and configuration.
    """

    id: str
    event_type: str
    goal_template: str
    priority: int = 50
    condition_type: str | None = None  # e.g., "payload_equals", "payload_contains"

    def to_trigger(self, condition_func: Callable[[AutonomousEvent], bool] | None = None) -> Trigger:
        """Convert to Trigger with condition function.

        Args:
            condition_func: Optional condition function

        Returns:
            Trigger instance
        """
        return Trigger(
            id=self.id,
            event_type=self.event_type,
            condition=condition_func,
            goal_template=self.goal_template,
            priority=self.priority,
        )
