"""Goal lifecycle events (RFC-1006)."""

from pydantic import BaseModel


class GoalCreated(BaseModel):
    """Emitted when a new goal is created."""

    goal_id: str
    description: str
    priority: int


class GoalUpdated(BaseModel):
    """Emitted when goal status is updated."""

    goal_id: str
    old_status: str
    new_status: str


class GoalCompleted(BaseModel):
    """Emitted when a goal is marked as completed."""

    goal_id: str
    description: str


class GoalFailed(BaseModel):
    """Emitted when a goal fails."""

    goal_id: str
    description: str
    error: str = ""
