"""
.. deprecated::
    The goalith module is deprecated and will be removed in a future release.
    Use TaskPlanner from noesium.agents.alithia.planner for goal decomposition.
    Use LangGraph StateGraph for workflow DAGs.
    Use ExecutionProjection for task state tracking.
"""

import warnings

warnings.warn(
    "noesium.core.goalith is deprecated. " "Use AlithiaAgent's TaskPlanner for goal decomposition.",
    DeprecationWarning,
    stacklevel=2,
)
