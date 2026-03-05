"""Subagent context for memory/state sharing between parent and subagent (RFC-1006 Section 5.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SubagentContext:
    """Context passed to subagents during initialization and execution.

    Enables memory sharing and configuration propagation between parent
    orchestrator and subagent.

    Attributes:
        session_id: Unique identifier for the execution session.
        parent_id: Identifier of the parent orchestrator agent.
        shared_memory: Memory bridge for parent-subagent context sharing (read/write).
        config: Configuration parameters passed from parent.
        depth: Current nesting depth for recursion control.
        max_depth: Maximum allowed nesting depth (from policy).
        permission_context: Security/permission context inherited from parent.
    """

    session_id: str
    parent_id: str
    shared_memory: Any = None
    config: dict[str, Any] = field(default_factory=dict)
    depth: int = 0
    max_depth: int = 5
    permission_context: dict[str, Any] = field(default_factory=dict)

    def can_spawn_child(self) -> bool:
        """Check if this context allows spawning a child subagent."""
        return self.depth < self.max_depth

    def child_context(
        self,
        child_session_id: str,
        *,
        config_overrides: dict[str, Any] | None = None,
    ) -> SubagentContext:
        """Create a child context for nested subagent invocation.

        Args:
            child_session_id: Session ID for the child subagent.
            config_overrides: Optional config overrides for the child.

        Returns:
            A new SubagentContext with incremented depth.

        Raises:
            RuntimeError: If max_depth would be exceeded.
        """
        if not self.can_spawn_child():
            raise RuntimeError(f"Cannot spawn child subagent: max depth {self.max_depth} reached")

        child_config = {**self.config}
        if config_overrides:
            child_config.update(config_overrides)

        return SubagentContext(
            session_id=child_session_id,
            parent_id=self.session_id,
            shared_memory=self.shared_memory,
            config=child_config,
            depth=self.depth + 1,
            max_depth=self.max_depth,
            permission_context=self.permission_context.copy(),
        )
