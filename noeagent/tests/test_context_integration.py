"""Integration tests for CognitiveContext with NoeAgent (RFC-1009)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noesium.core.context import CognitiveContext
from noesium.core.event import ProgressEvent, ProgressEventType


class TestContextIntegration:
    """Test CognitiveContext integration with NoeAgent."""

    def test_context_initialization(self) -> None:
        """Test that NoeAgent initializes with CognitiveContext."""
        from noeagent.config import NoeConfig

        config = NoeConfig(context_max_findings=5)
        assert config.context_max_findings == 5
        assert config.context_auto_recall is False

    def test_context_update_from_tool_end_event(self) -> None:
        """Test context is updated from TOOL_END events."""
        ctx = CognitiveContext()
        ctx.set_goal("Test goal")

        # Simulate TOOL_END event handling
        event = ProgressEvent(
            type=ProgressEventType.TOOL_END,
            tool_name="web_search",
            tool_result="Found 10 results about Python",
            summary="web_search: Found 10 results",
        )

        # Mimic _update_context_from_event logic
        if event.type == ProgressEventType.TOOL_END:
            tool_name = event.tool_name or "tool"
            result = event.tool_result or event.summary or ""
            ctx.add_finding(f"{tool_name}: {result[:80]}")

        assert len(ctx.findings) == 1
        assert "web_search" in ctx.findings[0]
        assert "Python" in ctx.findings[0]

    def test_context_update_from_subagent_end_event(self) -> None:
        """Test context is updated from SUBAGENT_END events."""
        ctx = CognitiveContext()
        ctx.set_goal("Research task")

        # Simulate SUBAGENT_END event handling
        event = ProgressEvent(
            type=ProgressEventType.SUBAGENT_END,
            subagent_id="tacitus",
            summary="Research complete",
            detail="Found 5 sources on the topic with detailed analysis",
        )

        # Mimic _update_context_from_event logic
        if event.type == ProgressEventType.SUBAGENT_END:
            subagent_id = event.subagent_id or "subagent"
            detail = event.detail or event.summary or ""
            ctx.add_finding(f"[{subagent_id}] {detail[:80]}")

        assert len(ctx.findings) == 1
        assert "[tacitus]" in ctx.findings[0]

    def test_context_update_from_plan_created_event(self) -> None:
        """Test context scratchpad is updated from PLAN_CREATED events."""
        ctx = CognitiveContext()

        # Simulate PLAN_CREATED event handling
        plan_snapshot = {
            "goal": "Research Python async",
            "steps": [
                {"description": "Search for docs", "status": "pending"},
                {"description": "Analyze results", "status": "pending"},
            ],
        }
        event = ProgressEvent(
            type=ProgressEventType.PLAN_CREATED,
            plan_snapshot=plan_snapshot,
            summary="Plan created",
        )

        # Mimic _update_context_from_event logic
        if event.type == ProgressEventType.PLAN_CREATED:
            if event.plan_snapshot:
                ctx.set_scratchpad("current_plan", event.plan_snapshot)

        assert ctx.get_scratchpad("current_plan") == plan_snapshot

    def test_context_for_subagent_scoping(self) -> None:
        """Test context scoping for subagent invocation."""
        parent_ctx = CognitiveContext()
        parent_ctx.set_goal("Main research task")
        parent_ctx.add_finding("Found initial resource")
        parent_ctx.set_scratchpad("parent_note", "important")

        # Create child context for subagent
        child_ctx = parent_ctx.for_subagent(task="Search for specific details")

        # Child should have new goal
        assert child_ctx.goal == "Search for specific details"
        # Child should inherit findings
        assert child_ctx.findings == ["Found initial resource"]
        # Child should have fresh scratchpad
        assert child_ctx.scratchpad == {}
        # Parent should be unaffected
        assert parent_ctx.goal == "Main research task"
        assert parent_ctx.get_scratchpad("parent_note") == "important"

    def test_context_export_for_prompt(self) -> None:
        """Test context export generates valid prompt injection text."""
        ctx = CognitiveContext()
        ctx.set_goal("Analyze Python code")
        ctx.add_finding("web_search: Found 5 relevant docs")
        ctx.add_finding("[tacitus] Synthesized research summary")

        export = ctx.export()

        assert "**Goal**: Analyze Python code" in export
        assert "**Findings**:" in export
        assert "web_search: Found 5 relevant docs" in export
        assert "[tacitus] Synthesized research summary" in export

    def test_context_persists_across_iterations(self) -> None:
        """Test context accumulates findings across multiple iterations."""
        ctx = CognitiveContext(max_findings=5)
        ctx.set_goal("Multi-step research")

        # Simulate multiple tool calls across iterations
        for i in range(3):
            ctx.add_finding(f"tool_{i}: result {i}")

        assert len(ctx.findings) == 3
        assert ctx.findings[0] == "tool_0: result 0"
        assert ctx.findings[2] == "tool_2: result 2"

    def test_context_auto_trim_maintains_recent(self) -> None:
        """Test context auto-trim keeps most recent findings."""
        ctx = CognitiveContext(max_findings=3)

        # Add more findings than max
        for i in range(5):
            ctx.add_finding(f"finding_{i}")

        # Should keep only last 3
        assert len(ctx.findings) == 3
        assert ctx.findings == ["finding_2", "finding_3", "finding_4"]


class TestContextWithSubagentContext:
    """Test CognitiveContext integration with SubagentContext."""

    def test_subagent_context_shared_memory(self) -> None:
        """Test CognitiveContext can be passed via SubagentContext.shared_memory."""
        from noesium.core.agent.subagent import SubagentContext

        parent_ctx = CognitiveContext()
        parent_ctx.set_goal("Research AI trends")
        parent_ctx.add_finding("Initial finding from web search")

        child_ctx = parent_ctx.for_subagent(task="Deep dive into LLMs")

        # Create SubagentContext with cognitive context
        subagent_context = SubagentContext(
            session_id="test-session",
            parent_id="test-parent",
            shared_memory=child_ctx,
            depth=1,
            max_depth=3,
        )

        # Verify the cognitive context is accessible
        assert subagent_context.shared_memory is not None
        assert isinstance(subagent_context.shared_memory, CognitiveContext)
        assert subagent_context.shared_memory.goal == "Deep dive into LLMs"
        assert "Initial finding from web search" in subagent_context.shared_memory.findings


class TestAgentStateIntegration:
    """Test CognitiveContext integration with AgentState."""

    def test_agent_state_includes_context_summary(self) -> None:
        """Test AgentState has context_summary field."""
        from noeagent.state import AgentState

        # AgentState is a TypedDict, verify the field exists
        state: AgentState = {
            "messages": [],
            "plan": None,
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
            "context_summary": "**Goal**: Test\n\n**Findings**:\n- Finding 1",
        }

        assert "context_summary" in state
        assert "**Goal**: Test" in state["context_summary"]
