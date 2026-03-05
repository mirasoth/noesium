"""Subagent descriptor and routing policy models (RFC-1006 Sections 5.1 and 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class BackendType(str, Enum):
    """Type of subagent execution backend."""

    INPROC = "inproc"
    BUILTIN = "builtin"
    CLI = "cli"
    REMOTE = "remote"


class CostHint(str, Enum):
    """Cost hint for subagent invocation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VARIABLE = "variable"


class LatencyHint(str, Enum):
    """Latency hint for subagent invocation."""

    INTERACTIVE = "interactive"
    BATCH = "batch"
    SLOW = "slow"


@dataclass
class SubagentDescriptor:
    """Static metadata describing a subagent's capabilities and constraints.

    Merges planner-facing metadata with runtime capability metadata in one
    authoritative descriptor.

    Attributes:
        subagent_id: Stable technical identifier (e.g., "browser_use", "tacitus").
        display_name: Human-readable name for UI display.
        description: Description of the subagent's purpose and capabilities.
        backend_type: Type of execution backend.
        task_types: List of task types this subagent can handle.
        keywords: Keywords for discovery and routing.
        requires_explicit_command: If True, cannot be auto-routed by LLM.
        supports_streaming: Whether subagent supports progress streaming.
        supports_parallel_invocation: Whether multiple concurrent invocations are allowed.
        max_concurrency: Maximum concurrent invocations (None for unlimited).
        cost_hint: Hint about resource cost.
        latency_hint: Hint about expected latency.
        input_schema: Optional JSON schema for extended input args.
        output_schema: Optional JSON schema for structured result.
        supports_hitl: Whether subagent can emit HITL requests.
    """

    subagent_id: str
    display_name: str
    description: str
    backend_type: BackendType | Literal["inproc", "builtin", "cli", "remote"]
    task_types: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    requires_explicit_command: bool = False
    supports_streaming: bool = True
    supports_parallel_invocation: bool = False
    max_concurrency: int | None = 1
    cost_hint: CostHint | Literal["low", "medium", "high", "variable"] = CostHint.MEDIUM
    latency_hint: LatencyHint | Literal["interactive", "batch", "slow"] = LatencyHint.BATCH
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    supports_hitl: bool = False

    def __post_init__(self) -> None:
        """Normalize enum values."""
        if isinstance(self.backend_type, str):
            self.backend_type = BackendType(self.backend_type)
        if isinstance(self.cost_hint, str):
            self.cost_hint = CostHint(self.cost_hint)
        if isinstance(self.latency_hint, str):
            self.latency_hint = LatencyHint(self.latency_hint)

    def matches_task_type(self, task_type: str) -> bool:
        """Check if this subagent can handle the given task type."""
        if not self.task_types:
            return True  # No restrictions
        return task_type in self.task_types

    def matches_keywords(self, query_keywords: list[str]) -> bool:
        """Check if any query keywords match this subagent's keywords."""
        if not query_keywords:
            return True
        return bool(set(self.keywords) & set(query_keywords))


@dataclass
class SubagentRoutingPolicy:
    """Policy constraints for subagent routing and invocation.

    Enforcement layers:
    1. Planner hinting: planner sees routeability metadata.
    2. Router validation: blocks invalid automatic routing.
    3. Runtime enforcement: hard fails if policy violated.

    Attributes:
        allow_auto_routing: Whether LLM can automatically route to this subagent.
        requires_explicit_command: Whether explicit user command is required.
        allowed_parent_agent_types: Types of parent agents that can invoke this.
        max_depth: Maximum nesting depth for this subagent.
        permission_profile: Named permission profile required for invocation.
        fallback_toolkits: Toolkits to suggest if this subagent cannot be invoked.
        deny_reasons: Reasons why routing may be denied.
    """

    allow_auto_routing: bool = True
    requires_explicit_command: bool = False
    allowed_parent_agent_types: list[str] = field(default_factory=list)
    max_depth: int = 5
    permission_profile: str = "default"
    fallback_toolkits: list[str] = field(default_factory=list)
    deny_reasons: list[str] = field(default_factory=list)

    def can_be_invoked_by(self, parent_agent_type: str, current_depth: int) -> bool:
        """Check if this subagent can be invoked by the given parent.

        Args:
            parent_agent_type: Type of the parent agent.
            current_depth: Current nesting depth.

        Returns:
            True if invocation is allowed by policy.
        """
        if current_depth >= self.max_depth:
            return False

        if self.allowed_parent_agent_types and parent_agent_type not in self.allowed_parent_agent_types:
            return False

        return True

    def validate_auto_routing(self) -> tuple[bool, str | None]:
        """Validate whether auto-routing is allowed.

        Returns:
            Tuple of (allowed, denial_reason).
        """
        if not self.allow_auto_routing:
            return False, "Auto-routing is disabled for this subagent"

        if self.requires_explicit_command:
            return False, "This subagent requires explicit user command"

        return True, None
