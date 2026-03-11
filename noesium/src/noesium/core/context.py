"""CognitiveContext: Minimal cognitive state for agent context continuity (RFC-1010).

Provides a lightweight 3-field model (goal, findings, scratchpad) for maintaining
context across TUI conversations and subagent interactions without event-sourcing
overhead. Includes context-window-aware finding generation and token-budgeted export.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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

    memory_manager: Any  # REQUIRED - ProviderMemoryManager instance (Any to allow mocks in tests)
    session_id: str  # REQUIRED for persistence key
    goal: str = ""
    findings: list[str] = Field(default_factory=list)
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    max_findings: int = 8
    auto_save: bool = True

    # ------------------------------------------------------------------
    # Core methods (RFC-1010 Section 6.1)
    # ------------------------------------------------------------------

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

    def export(self, include_scratchpad: bool = False, max_tokens: int | None = None) -> str:
        """Export context as markdown for prompt injection (RFC-1010 Section 9.1).

        Args:
            include_scratchpad: Include scratchpad contents (default False)
            max_tokens: Token budget; trims findings oldest-first when exceeded

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
            parts.append(f"**Scratchpad**: {json.dumps(self.scratchpad)}")

        result = "\n\n".join(parts) if parts else ""

        if max_tokens and self._estimate_tokens(result) > max_tokens:
            result = self._trim_to_budget(max_tokens)
        return result

    def for_subagent(self, task: str) -> "CognitiveContext":
        """Create a scoped context for a subagent (RFC-1010 Section 8.2).

        Inherits parent findings for continuity; fresh scratchpad to prevent
        plan pollution.

        Args:
            task: The specific task for the subagent

        Returns:
            New CognitiveContext with task as goal, inheriting findings
        """
        return CognitiveContext(
            memory_manager=self.memory_manager,
            session_id=f"{self.session_id}:subagent",
            goal=task,
            findings=self.findings.copy(),
            scratchpad={},
            max_findings=self.max_findings,
            auto_save=self.auto_save,
        )

    def clear(self) -> None:
        """Clear all context state."""
        self.goal = ""
        self.findings = []
        self.scratchpad = {}

    # ------------------------------------------------------------------
    # Memory integration (RFC-1010 Section 6.2) - MANDATORY
    # ------------------------------------------------------------------

    async def save(self, memory: Any = None, key: str | None = None) -> None:
        """Persist context to memory provider.

        Args:
            memory: Optional memory manager override (uses self.memory_manager by default)
            key: Storage key (defaults to "context:{session_id}")
        """
        from noesium.core.memory.provider import MemoryTier

        mgr = memory or self.memory_manager
        storage_key = key or f"context:{self.session_id}"
        await mgr.store(
            key=storage_key,
            value={
                "goal": self.goal,
                "findings": self.findings,
                "scratchpad": self.scratchpad,
                "max_findings": self.max_findings,
            },
            content_type="cognitive_context",
            tier=MemoryTier.PERSISTENT,
        )

    @classmethod
    async def from_memory(
        cls,
        memory: Any,
        key: str = "context",
        session_id: str = "",
        **kwargs: Any,
    ) -> "CognitiveContext":
        """Factory: create CognitiveContext restored from memory.

        Args:
            memory: Memory manager instance
            key: Storage key to load from
            session_id: Session identifier
            **kwargs: Additional CognitiveContext field overrides

        Returns:
            CognitiveContext instance with restored state
        """
        ctx = cls(memory_manager=memory, session_id=session_id, **kwargs)
        await ctx.load(key=key)
        return ctx

    async def load(self, memory: Any = None, key: str | None = None) -> bool:
        """Load context from memory.

        Args:
            memory: Optional memory manager override
            key: Storage key (defaults to "context:{session_id}")

        Returns:
            True if loaded successfully, False otherwise
        """
        mgr = memory or self.memory_manager
        storage_key = key or f"context:{self.session_id}"
        result = await mgr.read(storage_key)
        if result and isinstance(result.value, dict):
            self.goal = result.value.get("goal", "")
            self.findings = result.value.get("findings", [])
            self.scratchpad = result.value.get("scratchpad", {})
            self.max_findings = result.value.get("max_findings", 8)
            return True
        return False

    async def enrich(
        self,
        memory: Any = None,
        query: str | None = None,
        limit: int = 3,
    ) -> list[str]:
        """Enrich context with relevant memories (RFC-1010 Section 6.2).

        Args:
            memory: Optional memory manager override
            query: Search query (defaults to goal if not provided)
            limit: Max memories to recall

        Returns:
            List of recalled memory strings
        """
        from noesium.core.memory.provider import RecallQuery, RecallScope

        mgr = memory or self.memory_manager
        search_query = query or self.goal
        if not search_query:
            return []

        q = RecallQuery(query=search_query, scope=RecallScope.ALL, limit=limit)
        results = await mgr.recall(q)
        recalled: list[str] = []
        for r in results:
            value_str = str(r.entry.value)[:200]
            recalled.append(f"[memory] {value_str}")
            self.add_finding(f"[memory] {value_str}")

        return recalled

    # ------------------------------------------------------------------
    # Finding generation (RFC-1010 Section 13.3)
    # ------------------------------------------------------------------

    async def extract_finding(
        self,
        source: str,
        raw_result: str,
        *,
        llm: Any = None,
        mode: str = "smart",
        max_length: int = 200,
    ) -> str:
        """Extract a concise finding from a raw tool/subagent result.

        Args:
            source: Source identifier (e.g. tool name, subagent id)
            raw_result: The full raw result text
            llm: LLM client (required for mode="llm")
            mode: Extraction mode - "truncate", "smart", or "llm"
            max_length: Maximum character length of the full finding

        Returns:
            Formatted finding string
        """
        prefix = f"{source}: "
        available = max(max_length - len(prefix), 20)

        if len(raw_result) <= available:
            return f"{prefix}{raw_result}"

        if mode == "truncate":
            return f"{prefix}{raw_result[:available]}"

        if mode == "llm" and llm is not None:
            try:
                summary = await self._llm_summarize_result(llm, source, raw_result)
                return f"{prefix}{summary[:available]}"
            except Exception as exc:
                logger.debug("LLM finding extraction failed, falling back to smart: %s", exc)

        return f"{prefix}{self._smart_truncate(raw_result, available)}"

    async def consolidate_findings(self, llm: Any, keep_recent: int = 3) -> None:
        """Summarize oldest findings into a single [summary] entry via LLM.

        Replaces N old findings with one summary, keeping the most recent
        `keep_recent` findings intact (RFC-1010 Section 13.4).

        Args:
            llm: LLM client for summarization
            keep_recent: Number of recent findings to preserve
        """
        if len(self.findings) <= keep_recent + 1:
            return

        import asyncio

        old_findings = self.findings[:-keep_recent]
        recent = self.findings[-keep_recent:]
        old_text = "\n".join(f"- {f}" for f in old_findings)

        try:
            summary = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: llm.completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Summarize these research findings into 2-3 concise "
                                "bullet points. Preserve key facts and results."
                            ),
                        },
                        {"role": "user", "content": old_text},
                    ],
                    max_tokens=150,
                    temperature=0.0,
                ),
            )
            self.findings = [f"[summary] {str(summary).strip()}"] + recent
        except Exception as exc:
            logger.warning("Finding consolidation failed: %s", exc)

    # ------------------------------------------------------------------
    # Token estimation helpers (RFC-1010 Section 13.2)
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Approximate token count (~4 chars per token)."""
        return len(text) // 4

    def _trim_to_budget(self, max_tokens: int) -> str:
        """Rebuild export, dropping oldest findings until within token budget."""
        goal_part = f"**Goal**: {self.goal}" if self.goal else ""
        budget_used = self._estimate_tokens(goal_part)

        kept_findings: list[str] = []
        for finding in reversed(self.findings):
            line = f"- {finding}"
            line_tokens = self._estimate_tokens(line)
            if budget_used + line_tokens <= max_tokens:
                kept_findings.insert(0, line)
                budget_used += line_tokens
            else:
                break

        parts: list[str] = []
        if goal_part:
            parts.append(goal_part)
        if kept_findings:
            parts.append(f"**Findings**:\n" + "\n".join(kept_findings))
        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def _smart_truncate(text: str, max_length: int) -> str:
        """Truncate at sentence boundary when possible."""
        if len(text) <= max_length:
            return text
        for sep in [". ", ".\n", "\n\n", "\n"]:
            idx = text.rfind(sep, 0, max_length)
            if idx > max_length // 3:
                return text[: idx + 1].strip()
        return text[:max_length].strip() + "..."

    @staticmethod
    async def _llm_summarize_result(llm: Any, source: str, result: str) -> str:
        """Use LLM to summarize a verbose tool result into one sentence."""
        import asyncio

        truncated_input = result[:4000]
        summary = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm.completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Summarize this tool result in one concise sentence. " "Focus on the key finding or answer."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Tool: {source}\nResult:\n{truncated_input}",
                    },
                ],
                max_tokens=100,
                temperature=0.0,
            ),
        )
        return str(summary).strip()
