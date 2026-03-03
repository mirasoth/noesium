"""Integration tests for NoeAgent subagent spawning.

Tests cover:
- BrowserUse subagent integration
- CLI subagent integration (Claude CLI mock)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noesium.noeagent.config import (
    AgentSubagentConfig,
    CliSubagentConfig,
    NoeConfig,
    NoeMode,
)
from noesium.noeagent.progress import ProgressEvent, ProgressEventType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_config_with_subagents():
    """Create a NoeConfig with subagents enabled."""
    return NoeConfig(
        mode=NoeMode.AGENT,
        max_iterations=5,
        enabled_toolkits=[],
        enable_subagents=True,
        subagent_max_depth=2,
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation subagent",
                enabled=True,
            ),
        ],
        cli_subagents=[],
        enable_session_logging=False,
    )


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    llm = MagicMock()
    llm.completion = MagicMock(return_value="Test response")
    llm.structured_completion = MagicMock(return_value=MagicMock())
    return llm


# ---------------------------------------------------------------------------
# BrowserUse Subagent Tests
# ---------------------------------------------------------------------------


class TestBrowserUseSubagent:
    """Tests for BrowserUse subagent integration with NoeAgent."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_browser_use_subagent_config_available(self, minimal_config_with_subagents):
        """BrowserUse subagent should be available in config."""
        config = minimal_config_with_subagents

        browser_use_config = config.get_agent_subagent("browser_use")
        assert browser_use_config is not None
        assert browser_use_config["name"] == "browser_use"
        assert browser_use_config["agent_type"] == "browser_use"
        assert browser_use_config["enabled"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spawn_browser_use_subagent_disabled(self):
        """Spawning should fail when subagents are disabled."""
        from noesium.noeagent.agent import NoeAgent

        config = NoeConfig(
            mode=NoeMode.AGENT,
            enable_subagents=False,
        )
        agent = NoeAgent(config)

        with pytest.raises(RuntimeError, match="disabled"):
            await agent.spawn_subagent("browser_use")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spawn_browser_use_subagent_depth_limit(self):
        """Spawning should fail when depth limit is reached."""
        from noesium.noeagent.agent import NoeAgent

        config = NoeConfig(
            mode=NoeMode.AGENT,
            enable_subagents=True,
            subagent_max_depth=1,
        )
        agent = NoeAgent(config)
        agent._depth = 1  # Already at max depth

        with pytest.raises(RuntimeError, match="depth limit"):
            await agent.spawn_subagent("browser_use")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_spawn_child_subagent_success(self, minimal_config_with_subagents):
        """Successfully spawn a child NoeAgent subagent."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(minimal_config_with_subagents)
        agent.initialize = AsyncMock()

        # Spawn a child subagent
        subagent_id = await agent.spawn_subagent("web-searcher", mode=NoeMode.AGENT)

        assert subagent_id is not None
        assert "web-searcher" in subagent_id
        assert subagent_id in agent._subagents

        # Verify child agent has correct depth
        child = agent._subagents[subagent_id]
        assert child._depth == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_interact_with_subagent(self, minimal_config_with_subagents):
        """Interact with a spawned subagent."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(minimal_config_with_subagents)
        agent.initialize = AsyncMock()

        # Spawn subagent
        subagent_id = await agent.spawn_subagent("test-agent")

        # Mock the child's arun method
        child = agent._subagents[subagent_id]
        child.arun = AsyncMock(return_value="Task completed successfully")

        # Interact with subagent
        result = await agent.interact_with_subagent(subagent_id, "Do something")

        assert result == "Task completed successfully"
        child.arun.assert_awaited_once_with("Do something")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_subagent_events_in_progress_stream(self, minimal_config_with_subagents):
        """Subagent activity should emit progress events."""
        from langchain_core.messages import AIMessage

        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(minimal_config_with_subagents)
        agent.initialize = AsyncMock()

        mock_compiled = AsyncMock()

        # Simulate subagent spawn and result
        async def fake_astream(initial):
            yield {
                "subagent": {
                    "messages": [
                        AIMessage(
                            content="",
                            additional_kwargs={
                                "subagent_action": {
                                    "action": "spawn",
                                    "name": "browser-worker",
                                    "message": "Navigate to example.com",
                                    "mode": "agent",
                                }
                            },
                        )
                    ],
                    "tool_results": [],
                }
            }
            yield {"finalize": {"final_answer": "Browser task completed.", "messages": []}}

        mock_compiled.astream = fake_astream
        agent._build_graph = MagicMock()
        agent._build_graph.return_value.compile.return_value = mock_compiled

        events = []
        async for event in agent.astream_progress("Browse to example.com"):
            events.append(event)

        # Should have session lifecycle events
        event_types = [e.type for e in events]
        assert ProgressEventType.SESSION_START in event_types
        assert ProgressEventType.SESSION_END in event_types


# ---------------------------------------------------------------------------
# CLI Subagent Tests
# ---------------------------------------------------------------------------


class TestCliSubagent:
    """Tests for CLI subagent integration (e.g., Claude CLI)."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cli_subagent_config(self):
        """CLI subagent configuration should be properly set."""
        config = NoeConfig(
            mode=NoeMode.AGENT,
            cli_subagents=[
                CliSubagentConfig(
                    name="claude",
                    command="claude",
                    args=["--output-format", "stream-json"],
                    timeout=300,
                    task_types=["code_edit", "code_review"],
                ),
            ],
        )

        assert len(config.cli_subagents) == 1
        cli_config = config.cli_subagents[0]
        assert cli_config.name == "claude"
        assert cli_config.command == "claude"
        assert cli_config.timeout == 300
        assert "code_edit" in cli_config.task_types

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cli_adapter_spawn_mock(self, minimal_config_with_subagents):
        """Test CLI adapter spawn with mocked subprocess."""
        from noesium.noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        cli_config = CliSubagentConfig(
            name="test-cli",
            command="echo",
            args=["test"],
            timeout=10,
        )

        with patch.object(asyncio, "create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.stdin = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stderr = MagicMock()
            mock_proc.returncode = None
            mock_spawn.return_value = mock_proc

            result = await adapter.spawn_from_config(cli_config)

            assert "spawned" in result.lower()
            assert adapter.get_handle("test-cli") is not None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cli_adapter_interact_mock(self):
        """Test CLI adapter interaction with mocked process."""
        from noesium.noeagent.cli_adapter import ExternalCliAdapter, SubagentHandle

        adapter = ExternalCliAdapter()

        # Set up a mock handle and process
        cli_config = CliSubagentConfig(
            name="test-cli",
            command="test",
            timeout=10,
        )

        handle = SubagentHandle(
            name="test-cli",
            config=cli_config,
            session_id="test-session",
            state="RUNNING",
            pid=12345,
        )
        adapter._handles["test-cli"] = handle

        # Mock process with async methods
        mock_proc = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock()
        mock_stdin.drain = AsyncMock()
        mock_proc.stdin = mock_stdin
        mock_proc.stdout = MagicMock()

        # Mock the readline to return a JSON response
        import json

        response_json = json.dumps({"result": "CLI task completed"})
        mock_proc.stdout.readline = AsyncMock(return_value=response_json.encode() + b"\n")
        adapter._processes["test-cli"] = mock_proc

        result = await adapter.interact("test-cli", "Do something")

        assert result == "CLI task completed"
        mock_stdin.write.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cli_adapter_terminate(self):
        """Test CLI adapter termination."""
        from noesium.noeagent.cli_adapter import ExternalCliAdapter, SubagentHandle

        adapter = ExternalCliAdapter()

        cli_config = CliSubagentConfig(
            name="test-cli",
            command="test",
            timeout=10,
        )

        handle = SubagentHandle(
            name="test-cli",
            config=cli_config,
            session_id="test-session",
            state="RUNNING",
            pid=12345,
        )
        adapter._handles["test-cli"] = handle

        # Mock process
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.wait = AsyncMock()
        adapter._processes["test-cli"] = mock_proc

        result = await adapter.terminate("test-cli")

        assert "terminated" in result.lower()
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cli_adapter_command_not_found(self):
        """CLI adapter should handle missing command gracefully."""
        from noesium.noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        cli_config = CliSubagentConfig(
            name="nonexistent",
            command="this-command-does-not-exist-12345",
            timeout=10,
        )

        result = await adapter.spawn_from_config(cli_config)

        assert "not found" in result.lower() or "failed" in result.lower()


# ---------------------------------------------------------------------------
# Integration Tests with NoeAgent
# ---------------------------------------------------------------------------


class TestNoeAgentCliSubagentIntegration:
    """Tests for NoeAgent integration with CLI subagents."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_noeagent_sets_up_cli_subagents(self):
        """NoeAgent should set up CLI subagents on initialization."""
        from noesium.noeagent.agent import NoeAgent
        from noesium.noeagent.cli_adapter import ExternalCliAdapter

        config = NoeConfig(
            mode=NoeMode.AGENT,
            cli_subagents=[
                CliSubagentConfig(
                    name="claude-mock",
                    command="echo",
                    args=["mock"],
                    timeout=10,
                ),
            ],
            enable_session_logging=False,
        )

        # Mock the ExternalCliAdapter class
        with patch.object(ExternalCliAdapter, "spawn_from_config", new_callable=AsyncMock) as mock_spawn:
            mock_spawn.return_value = "spawned"

            agent = NoeAgent(config)
            await agent._setup_cli_subagents()

            # Verify adapter was created
            assert agent._cli_adapter is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_subagent_cleanup_on_session_end(self, minimal_config_with_subagents):
        """Subagents should be cleaned up when session ends."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(minimal_config_with_subagents)
        agent.initialize = AsyncMock()

        # Spawn a subagent
        subagent_id = await agent.spawn_subagent("test")
        assert subagent_id in agent._subagents

        # Call cleanup
        await agent._cleanup_subagents()

        # Verify cleanup
        assert len(agent._subagents) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_nested_subagent_depth(self, minimal_config_with_subagents):
        """Nested subagents should have correct depth tracking."""
        from noesium.noeagent.agent import NoeAgent

        config = NoeConfig(
            mode=NoeMode.AGENT,
            enable_subagents=True,
            subagent_max_depth=3,
            enable_session_logging=False,
        )

        parent = NoeAgent(config)
        parent.initialize = AsyncMock()
        parent._depth = 0

        # Spawn first level child
        child1_id = await parent.spawn_subagent("level1")
        child1 = parent._subagents[child1_id]
        assert child1._depth == 1

        # Spawn second level child from child1
        child2_id = await child1.spawn_subagent("level2")
        child2 = child1._subagents[child2_id]
        assert child2._depth == 2

        # Third level should still work
        child3_id = await child2.spawn_subagent("level3")
        child3 = child2._subagents[child3_id]
        assert child3._depth == 3

        # Fourth level should fail (exceeds max_depth=3)
        with pytest.raises(RuntimeError, match="depth limit"):
            await child3.spawn_subagent("level4")


# ---------------------------------------------------------------------------
# Progress Event Tests for Subagents
# ---------------------------------------------------------------------------


class TestSubagentProgressEvents:
    """Tests for subagent-related progress events."""

    @pytest.mark.unit
    def test_subagent_start_event(self):
        """SUBAGENT_START event should have required fields."""
        event = ProgressEvent(
            type=ProgressEventType.SUBAGENT_START,
            subagent_id="browser-worker-1",
            summary="Spawning browser subagent",
        )

        assert event.type == ProgressEventType.SUBAGENT_START
        assert event.subagent_id == "browser-worker-1"
        assert "browser" in event.summary.lower()

    @pytest.mark.unit
    def test_subagent_progress_event(self):
        """SUBAGENT_PROGRESS event should track ongoing work."""
        event = ProgressEvent(
            type=ProgressEventType.SUBAGENT_PROGRESS,
            subagent_id="browser-worker-1",
            summary="Navigating to example.com",
        )

        assert event.type == ProgressEventType.SUBAGENT_PROGRESS
        assert event.subagent_id == "browser-worker-1"

    @pytest.mark.unit
    def test_subagent_end_event(self):
        """SUBAGENT_END event should indicate completion."""
        event = ProgressEvent(
            type=ProgressEventType.SUBAGENT_END,
            subagent_id="browser-worker-1",
            summary="Browser task completed successfully",
        )

        assert event.type == ProgressEventType.SUBAGENT_END
        assert "completed" in event.summary.lower()
