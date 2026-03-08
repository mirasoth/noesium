"""Goal lifecycle domain events (RFC-1006)."""

from noesium.core.event.types import DomainEvent


class GoalCreated(DomainEvent):
    """Emitted when a new goal is created."""

    goal_id: str
    description: str
    priority: int

    def event_type(self) -> str:
        return "goal.created"


class GoalUpdated(DomainEvent):
    """Emitted when goal status is updated."""

    goal_id: str
    old_status: str
    new_status: str

    def event_type(self) -> str:
        return "goal.updated"


class GoalCompleted(DomainEvent):
    """Emitted when a goal is marked as completed."""

    goal_id: str
    description: str

    def event_type(self) -> str:
        return "goal.completed"


class GoalFailed(DomainEvent):
    """Emitted when a goal fails."""

    goal_id: str
    description: str
    error: str = ""

    def event_type(self) -> str:
        return "goal.failed"
