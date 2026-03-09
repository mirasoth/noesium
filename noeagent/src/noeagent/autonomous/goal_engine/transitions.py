"""Goal state transition validation (RFC-1006 §9)."""

from noeagent.autonomous.goal_engine.models import GoalStatus

VALID_TRANSITIONS: dict[GoalStatus, set[GoalStatus]] = {
    GoalStatus.PENDING: {GoalStatus.ACTIVE, GoalStatus.BLOCKED},
    GoalStatus.ACTIVE: {GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.BLOCKED},
    GoalStatus.BLOCKED: {GoalStatus.ACTIVE, GoalStatus.FAILED},
    GoalStatus.COMPLETED: set(),
    GoalStatus.FAILED: set(),
}


def is_valid_transition(from_status: GoalStatus, to_status: GoalStatus) -> bool:
    """Check if state transition is valid.

    Args:
        from_status: Current status
        to_status: Target status

    Returns:
        True if transition is allowed
    """
    valid_targets = VALID_TRANSITIONS.get(from_status, set())
    return to_status in valid_targets


def get_valid_transitions(status: GoalStatus) -> set[GoalStatus]:
    """Get all valid target states from current status.

    Args:
        status: Current status

    Returns:
        Set of valid target statuses
    """
    return VALID_TRANSITIONS.get(status, set())
