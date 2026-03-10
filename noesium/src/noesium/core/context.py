"""CognitiveContext: Minimal cognitive state for agent context continuity (RFC-1009).

Provides a lightweight 3-field model (goal, findings, scratchpad) for maintaining
context across TUI conversations and subagent interactions without event-sourcing overhead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from noesium.core.memory.provider_manager import ProviderMemoryManager


class CognitiveContext(BaseModel):
    """Minimal cognitive state for agent context continuity.

    Memory persistence is MANDATORY. All instances must have memory_manager and session_id.

    Attributes:
        memory_manager: REQUIRED - Memory manager for persistence (mandatory)
        session_id: REQUIRED - Unique identifier for this session (used as persistence key)
        goal: Current task/question the agent is working on
        findings: Recent discoveries/results (auto-trimmed to max_findings)
        scratchpad: Flexible key-value store for intermediate state
        max_findings: Maximum number of findings to retain (FIFO)
        auto_save: Automatically save context on changes (default True)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    memory_manager: "ProviderMemoryManager"  # REQUIRED
    session_id: str  # REQUIRED for persistence key
    goal: str = ""
    findings: list[str] = Field(default_factory=list)
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    max_findings: int = 8
    auto_save: bool = True

    def set_goal(self, goal: str) -> None:
        """Set the current goal/task."""
        self.goal = goal

    def add_finding(self, finding: str) -> None:
        """Add a finding with auto-trim to max_findings (FIFO)."""
        self.findings.append(finding)
        if len(self.findings) > self.max_findings:
            self.findings = self.findings[-self.max_findings :]

    def set_scratchpad(self, key: str, value: Any) -> None:
        """Set a scratchpad key-value pair."""
        self.scratchpad[key] = value

    def get_scratchpad(self, key: str, default: Any = None) -> Any:
        """Get a scratchpad value with optional default."""
        return self.scratchpad.get(key, default)

    def export(self, include_scratchpad: bool = False) -> str:
        """Export context as a string for prompt injection.

        Args:
            include_scratchpad: Include scratchpad contents (default False)

        Returns:
            Formatted string representation of context
        """
        parts: list[str] = []

        if self.goal:
            parts.append(f"**Goal**: {self.goal}")

        if self.findings:
            findings_str = "\n".join(f"- {f}" for f in self.findings)
            parts.append(f"**Findings**:\n{findings_str}")

        if include_scratchpad and self.scratchpad:
            scratchpad_items = "\n".join(f"- {k}: {v}" for k, v in self.scratchpad.items())
            parts.append(f"**Notes**:\n{scratchpad_items}")

        return "\n\n".join(parts) if parts else ""

    def for_subagent(self, task: str) -> "CognitiveContext":
        """Create a scoped context for a subagent.

        Args:
            task: The specific task for the subagent

        Returns:
            New CognitiveContext with task as goal, inheriting findings
        """
        return CognitiveContext(
            memory_manager=self.memory_manager,
            session_id=f"{self.session_id}:subagent",
            goal=task,
            findings=self.findings.copy(),  # Inherit parent findings
            scratchpad={},  # Fresh scratchpad for subagent
            max_findings=self.max_findings,
            auto_save=self.auto_save,
        )

    def clear(self) -> None:
        """Clear all context state."""
        self.goal = ""
        self.findings = []
        self.scratchpad = {}

    # Memory integration methods (MANDATORY)

    async def save(self, key: str | None = None) -> None:
        """Save context to memory (mandatory persistence).

        Args:
            key: Storage key (defaults to "context:{session_id}")
        """
        storage_key = key or f"context:{self.session_id}"
        await self.memory_manager.store(
            key=storage_key,
            value={
                "goal": self.goal,
                "findings": self.findings,
                "scratchpad": self.scratchpad,
                "max_findings": self.max_findings,
            },
            content_type="cognitive_context",
        )

    async def load(self, key: str | None = None) -> bool:
        """Load context from memory (mandatory restore).

        Args:
            key: Storage key (defaults to "context:{session_id}")

        Returns:
            True if loaded successfully, False otherwise
        """
        storage_key = key or f"context:{self.session_id}"
        result = await self.memory_manager.read(storage_key)
        if result and isinstance(result.value, dict):
            self.goal = result.value.get("goal", "")
            self.findings = result.value.get("findings", [])
            self.scratchpad = result.value.get("scratchpad", {})
            self.max_findings = result.value.get("max_findings", 8)
            return True
        return False

    async def enrich(
        self,
        query: str | None = None,
        limit: int = 3,
    ) -> list[str]:
        """Enrich context with relevant memories.

        Args:
            query: Search query (defaults to goal if not provided)
            limit: Max memories to recall

        Returns:
            List of recalled memory strings
        """
        search_query = query or self.goal
        if not search_query:
            return []

        results = await self.memory_manager.recall(search_query, limit=limit)
        recalled: list[str] = []
        for r in results:
            value_str = str(r.entry.value)[:200]  # Truncate long values
            recalled.append(f"[memory] {value_str}")
            self.add_finding(f"[memory] {value_str}")

        return recalled
