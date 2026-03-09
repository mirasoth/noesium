"""Goal Engine module for autonomous agents (RFC-1006)."""

from .engine import GoalEngine
from .events import GoalCompleted, GoalCreated, GoalFailed, GoalUpdated
from .models import Goal, GoalStatus

__all__ = [
    "Goal",
    "GoalStatus",
    "GoalEngine",
    "GoalCreated",
    "GoalUpdated",
    "GoalCompleted",
    "GoalFailed",
]
