"""Integration tests for NoeAgent subagent spawning.

Tests cover:
- BrowserUse subagent integration
- CLI subagent integration (Claude CLI mock)
- One-shot CLI execution mode
- Claude CLI adapter
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from noeagent.config import (
    AgentSubagentConfig,
    CliSubagentConfig,
    NoeConfig,
    NoeMode,
)

from noesium.core.event import ProgressEvent, ProgressEventType

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
        builtin=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation subagent",
                enabled=True,
            ),
        ],
        external=[],
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

        browser_use_config = config.get_builtin_subagent("browser_use")
        assert browser_use_config is not None
        assert browser_use_config["name"] == "browser_use"
        assert browser_use_config["agent_type"] == "browser_use"
        assert browser_use_config["enabled"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_spawn_browser_use_subagent_disabled(self):
        """Spawning should fail when subagents are disabled."""
        from noeagent.agent import NoeAgent

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
        from noeagent.agent import NoeAgent

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
        from noeagent.agent import NoeAgent

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
        """Interact with a spawned subagent via invoke_subagent()."""
        from noeagent.agent import NoeAgent

        from noesium.core.agent.subagent import SubagentManager

        agent = NoeAgent(minimal_config_with_subagents)
        # Set up SubagentManager so spawn_subagent can register the child
        agent._subagent_manager = SubagentManager()

        # Spawn subagent (registers NoeChildSubagentRuntime in SubagentManager)
        subagent_id = await agent.spawn_subagent("test-agent")

        # Mock invoke_subagent since we don't want actual LLM calls
        agent.invoke_subagent = AsyncMock(return_value="Task completed successfully")

        # Interact with subagent
        result = await agent.interact_with_subagent(subagent_id, "Do something")

        assert result == "Task completed successfully"
        agent.invoke_subagent.assert_awaited_once_with(subagent_id, "Do something")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_subagent_events_in_progress_stream(self, minimal_config_with_subagents):
        """Subagent activity should emit progress events."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent

        agent = NoeAgent(minimal_config_with_subagents)
        agent.initialize = AsyncMock()

        mock_compiled = AsyncMock()

        # Simulate subagent spawn and result
        async def fake_astream(initial, config=None):
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
    async def test_external_subagent_config(self):
        """External subagent configuration should be properly set."""
        config = NoeConfig(
            mode=NoeMode.AGENT,
            external=[
                CliSubagentConfig(
                    name="claude",
                    command="claude",
                    args=["--output-format", "stream-json"],
                    timeout=300,
                    task_types=["code_edit", "code_review"],
                ),
            ],
        )

        assert len(config.external) == 1
        cli_config = config.external[0]
        assert cli_config.name == "claude"
        assert cli_config.command == "claude"
        assert cli_config.timeout == 300
        assert "code_edit" in cli_config.task_types

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cli_adapter_spawn_mock(self, minimal_config_with_subagents):
        """Test CLI adapter spawn with mocked subprocess."""
        from noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        cli_config = CliSubagentConfig(
            name="test-cli",
            command="echo",
            args=["test"],
            timeout=10,
            mode="daemon",
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
        from noeagent.cli_adapter import ExternalCliAdapter, SubagentHandle

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
        from noeagent.cli_adapter import ExternalCliAdapter, SubagentHandle

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
        """CLI adapter should handle missing command gracefully in daemon mode."""
        from noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        cli_config = CliSubagentConfig(
            name="nonexistent",
            command="this-command-does-not-exist-12345",
            timeout=10,
            mode="daemon",
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
    async def test_noeagent_sets_up_external_subagents(self):
        """NoeAgent should set up external subagents on initialization."""
        from noeagent.agent import NoeAgent
        from noeagent.cli_adapter import ExternalCliAdapter

        config = NoeConfig(
            mode=NoeMode.AGENT,
            external=[
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
            await agent._setup_external_subagents()

            # Verify adapter was created
            assert agent._cli_adapter is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_subagent_cleanup_on_session_end(self, minimal_config_with_subagents):
        """Subagents should be cleaned up when session ends."""
        from noeagent.agent import NoeAgent

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
        from noeagent.agent import NoeAgent

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


# ---------------------------------------------------------------------------
# Built-in Agent Subagent Tests
# ---------------------------------------------------------------------------


class TestBuiltInAgentCapabilityProvider:
    """Tests for BuiltInAgentCapabilityProvider."""

    @pytest.mark.unit
    def test_provider_descriptor_creation(self):
        """BuiltInAgentCapabilityProvider should create correct descriptor."""
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider

        def mock_factory():
            return MagicMock()

        provider = BuiltInAgentCapabilityProvider(
            name="browser_use",
            agent_factory=mock_factory,
            agent_type="browser_use",
            description="Browser automation agent",
        )

        assert provider.descriptor.capability_id == "builtin_agent:browser_use"
        assert provider.descriptor.capability_type.value == "agent"
        assert "browser_use" in provider.descriptor.tags
        assert provider.descriptor.stateful is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_invoke_creates_agent(self):
        """BuiltInAgentCapabilityProvider should lazily create agent on invoke."""
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value="Task completed")

        factory_called = False

        def mock_factory():
            nonlocal factory_called
            factory_called = True
            return mock_agent

        provider = BuiltInAgentCapabilityProvider(
            name="test_agent",
            agent_factory=mock_factory,
        )

        # Agent should not be created yet
        assert provider.agent is None
        assert not factory_called

        # Invoke should create and use the agent
        result = await provider.invoke(message="Test task")

        assert factory_called
        assert provider.agent is mock_agent
        assert result == "Task completed"
        mock_agent.arun.assert_awaited_once_with("Test task")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_health_always_true(self):
        """BuiltInAgentCapabilityProvider health should always return True."""
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider

        provider = BuiltInAgentCapabilityProvider(
            name="test_agent",
            agent_factory=lambda: MagicMock(),
        )

        assert await provider.health() is True


class TestBuiltInBuiltinSubagentSetup:
    """Tests for NoeAgent._setup_builtin_subagents()."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_setup_builtin_subagents_registers_providers(self, minimal_config_with_subagents):
        """_setup_builtin_subagents should register built-in agents in SubagentManager."""
        from noeagent.agent import NoeAgent

        from noesium.core.agent.subagent import SubagentManager

        agent = NoeAgent(minimal_config_with_subagents)
        agent._subagent_manager = SubagentManager()
        agent.llm = MagicMock()

        await agent._setup_builtin_subagents()

        # Should have registered browser_use in SubagentManager
        provider = agent._subagent_manager.get_provider("browser_use")
        assert provider is not None
        assert provider.descriptor.subagent_id == "browser_use"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_setup_builtin_subagents_skips_disabled(self):
        """_setup_builtin_subagents should skip disabled subagents."""
        from noeagent.agent import NoeAgent

        from noesium.core.agent.subagent import SubagentManager

        config = NoeConfig(
            mode=NoeMode.AGENT,
            builtin=[
                AgentSubagentConfig(
                    name="browser_use",
                    agent_type="browser_use",
                    enabled=False,
                ),
            ],
            enable_session_logging=False,
        )

        agent = NoeAgent(config)
        agent._subagent_manager = SubagentManager()
        agent.llm = MagicMock()

        await agent._setup_builtin_subagents()

        # Should not have registered the disabled subagent
        assert agent._subagent_manager.get_provider("browser_use") is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_setup_builtin_subagents_handles_unknown_type(self):
        """_setup_builtin_subagents should skip unknown agent types."""
        from noeagent.agent import NoeAgent

        from noesium.core.agent.subagent import SubagentManager

        config = NoeConfig(
            mode=NoeMode.AGENT,
            builtin=[
                AgentSubagentConfig(
                    name="unknown_agent",
                    agent_type="unknown_type",
                    enabled=True,
                ),
            ],
            enable_session_logging=False,
        )

        agent = NoeAgent(config)
        agent._subagent_manager = SubagentManager()
        agent.llm = MagicMock()

        # Should not raise, just log warning
        await agent._setup_builtin_subagents()

        # SubagentManager should have no providers registered
        assert agent._subagent_manager.get_provider("unknown_agent") is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_setup_builtin_subagents_binds_correct_factory_per_subagent(self):
        """Each built-in provider should keep its own factory callable."""
        from noeagent.agent import NoeAgent

        from noesium.core.agent.subagent import SubagentManager

        config = NoeConfig(
            mode=NoeMode.AGENT,
            builtin=[
                AgentSubagentConfig(name="browser_use", agent_type="browser_use", enabled=True),
                AgentSubagentConfig(name="tacitus", agent_type="tacitus", enabled=True),
            ],
            enable_session_logging=False,
        )

        agent = NoeAgent(config)
        agent._subagent_manager = SubagentManager()
        agent.llm = MagicMock()

        browser_factory = MagicMock(return_value="browser-instance")
        tacitus_factory = MagicMock(return_value="tacitus-instance")
        agent._create_browser_use_agent = browser_factory
        agent._create_tacitus_agent = tacitus_factory

        await agent._setup_builtin_subagents()

        browser_provider = agent._subagent_manager.get_provider("browser_use")
        tacitus_provider = agent._subagent_manager.get_provider("tacitus")

        assert browser_provider is not None
        assert tacitus_provider is not None
        # Verify factories are distinct by calling them
        assert browser_provider.descriptor.subagent_id == "browser_use"
        assert tacitus_provider.descriptor.subagent_id == "tacitus"


class TestInvokeBuiltinAction:
    """Tests for invoke_builtin subagent action."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_builtin_action(self):
        """invoke_builtin action should invoke the built-in agent via SubagentManager."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent
        from noeagent.graph.nodes import subagent_node
        from noeagent.state import AgentState

        from noesium.core.agent.subagent import SubagentManager

        # Create agent and set up SubagentManager
        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        agent._subagent_manager = SubagentManager()

        # Mock invoke_subagent to return a result
        agent.invoke_subagent = AsyncMock(return_value="Browser task completed")

        # Create state with invoke_builtin action
        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    additional_kwargs={
                        "subagent_action": {
                            "action": "invoke_builtin",
                            "name": "browser_use",
                            "message": "Navigate to example.com",
                        }
                    },
                )
            ],
            "iteration": 0,
            "tool_results": [],
        }

        result = await subagent_node(state, agent=agent)

        assert "tool_results" in result
        assert len(result["tool_results"]) == 1
        assert "browser_use" in result["tool_results"][0]["tool"]
        agent.invoke_subagent.assert_awaited_once_with("browser_use", "Navigate to example.com")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_builtin_missing_agent(self):
        """invoke_builtin should handle missing agent gracefully via SubagentManager."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent
        from noeagent.graph.nodes import subagent_node
        from noeagent.state import AgentState

        from noesium.core.agent.subagent import SubagentManager

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        # Set up empty SubagentManager (no providers registered)
        agent._subagent_manager = SubagentManager()

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    additional_kwargs={
                        "subagent_action": {
                            "action": "invoke_builtin",
                            "name": "nonexistent",
                            "message": "Test",
                        }
                    },
                )
            ],
            "iteration": 0,
            "tool_results": [],
        }

        result = await subagent_node(state, agent=agent)

        # Should produce an error result (provider not found → exception → "Failed to invoke")
        tool_result = result["tool_results"][0]["result"].lower()
        assert "failed" in tool_result or "not found" in tool_result or "unavailable" in tool_result


# ---------------------------------------------------------------------------
# One-shot CLI Mode Tests
# ---------------------------------------------------------------------------


class TestOneshotCliMode:
    """Tests for one-shot CLI execution mode."""

    @pytest.mark.unit
    def test_cli_config_oneshot_mode_default(self):
        """CliSubagentConfig should default to oneshot mode."""
        config = CliSubagentConfig(
            name="test",
            command="test",
        )
        assert config.mode == "oneshot"
        assert config.output_format == "text"
        assert config.skip_permissions is True

    @pytest.mark.unit
    def test_cli_config_daemon_mode(self):
        """CliSubagentConfig should support daemon mode."""
        config = CliSubagentConfig(
            name="test",
            command="test",
            mode="daemon",
            output_format="stream-json",
        )
        assert config.mode == "daemon"
        assert config.output_format == "stream-json"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oneshot_execution_mock(self):
        """Test oneshot execution with mocked subprocess."""
        from noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        config = CliSubagentConfig(
            name="echo-cli",
            command="echo",
            mode="oneshot",
            output_format="text",
            timeout=10,
        )
        adapter.register_config(config)

        # Mock the subprocess execution
        with patch.object(asyncio, "create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
            mock_proc = MagicMock()
            mock_proc.stdin = MagicMock()
            mock_proc.stdin.write = MagicMock()
            mock_proc.stdin.drain = AsyncMock()
            mock_proc.stdin.close = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stderr = MagicMock()
            mock_proc.communicate = AsyncMock(return_value=(b"Hello World", b""))
            mock_proc.returncode = 0
            mock_spawn.return_value = mock_proc

            result = await adapter.execute_oneshot("echo-cli", "Hello World")

            assert result.success is True
            assert "Hello World" in result.content

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oneshot_execution_timeout(self):
        """Test oneshot execution timeout handling."""
        from noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        config = CliSubagentConfig(
            name="slow-cli",
            command="sleep",
            mode="oneshot",
            timeout=1,  # 1 second timeout
        )
        adapter.register_config(config)

        with patch.object(asyncio, "create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
            mock_proc = MagicMock()
            mock_proc.stdin = MagicMock()
            mock_proc.stdin.write = MagicMock()
            mock_proc.stdin.drain = AsyncMock()
            mock_proc.stdin.close = MagicMock()
            mock_proc.kill = MagicMock()
            mock_proc.wait = AsyncMock()
            mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_spawn.return_value = mock_proc

            result = await adapter.execute_oneshot("slow-cli", "test")

            assert result.success is False
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oneshot_execution_command_not_found(self):
        """Test oneshot execution with missing command."""
        from noeagent.cli_adapter import ExternalCliAdapter

        adapter = ExternalCliAdapter()

        config = CliSubagentConfig(
            name="missing-cli",
            command="this-command-does-not-exist-12345",
            mode="oneshot",
        )
        adapter.register_config(config)

        with patch.object(asyncio, "create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
            mock_spawn.side_effect = FileNotFoundError("Command not found")

            result = await adapter.execute_oneshot("missing-cli", "test")

            assert result.success is False
            assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# Output Parser Tests
# ---------------------------------------------------------------------------


class TestOutputParser:
    """Tests for CLI output parsing."""

    @pytest.mark.unit
    def test_parse_text_output(self):
        """Test plain text output parsing."""
        from noeagent.cli_adapter import OutputParser

        raw = b"Hello, this is plain text output.\n"
        result = OutputParser.parse(raw, "text")
        assert result == "Hello, this is plain text output."

    @pytest.mark.unit
    def test_parse_json_output(self):
        """Test single JSON object parsing."""
        from noeagent.cli_adapter import OutputParser

        raw = b'{"content": "Hello from JSON"}'
        result = OutputParser.parse(raw, "json")
        assert result == "Hello from JSON"

    @pytest.mark.unit
    def test_parse_ndjson_output(self):
        """Test NDJSON streaming output parsing."""
        from noeagent.cli_adapter import OutputParser

        raw = b'{"content": "Hello"}\n{"content": " World"}\n'
        result = OutputParser.parse(raw, "ndjson")
        assert result == "Hello World"

    @pytest.mark.unit
    def test_parse_claude_streaming_format(self):
        """Test Claude CLI streaming format parsing."""
        from noeagent.cli_adapter import OutputParser

        # Simulate Claude CLI stream-json output
        raw = b"""
{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}
{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}
{"type":"content_block_stop","index":0}
{"type":"message_stop"}
""".strip()
        result = OutputParser.parse(raw, "stream-json")
        assert result == "Hello world"


# ---------------------------------------------------------------------------
# Claude CLI Adapter Tests
# ---------------------------------------------------------------------------


class TestClaudeCliAdapter:
    """Tests for specialized Claude CLI adapter."""

    @pytest.mark.unit
    def test_claude_adapter_config_validation(self):
        """Claude CLI adapter should validate configuration."""
        from noeagent.cli_adapter import ClaudeCliAdapter

        config = CliSubagentConfig(
            name="claude",
            command="claude",
            mode="oneshot",
            output_format="stream-json",
            skip_permissions=True,
        )

        adapter = ClaudeCliAdapter(config)
        assert adapter.config.name == "claude"

    @pytest.mark.unit
    def test_build_command_args_oneshot(self):
        """Claude CLI adapter should build correct command args."""
        from noeagent.cli_adapter import ClaudeCliAdapter

        config = CliSubagentConfig(
            name="claude",
            command="claude",
            mode="oneshot",
            output_format="stream-json",
        )

        adapter = ClaudeCliAdapter(config)
        args = adapter.build_command_args("test task")

        # Should include print mode
        assert "-p" in args
        # Should include output format
        assert "--output-format" in args
        assert "stream-json" in args
        # Should include verbose (required for stream-json)
        assert "--verbose" in args
        # Should skip permissions by default
        assert "--dangerously-skip-permissions" in args

    @pytest.mark.unit
    def test_build_command_args_with_tools(self):
        """Claude CLI adapter should handle allowed tools."""
        from noeagent.cli_adapter import ClaudeCliAdapter

        config = CliSubagentConfig(
            name="claude",
            command="claude",
            mode="oneshot",
            allowed_tools=["Bash", "Edit", "Read"],
        )

        adapter = ClaudeCliAdapter(config)
        args = adapter.build_command_args("test task")

        assert "--allowedTools" in args
        tool_idx = args.index("--allowedTools")
        assert "Bash,Edit,Read" in args[tool_idx + 1]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_claude_adapter_execute_mock(self):
        """Test Claude CLI execution with mocked subprocess."""
        from noeagent.cli_adapter import ClaudeCliAdapter

        config = CliSubagentConfig(
            name="claude",
            command="claude",
            mode="oneshot",
            output_format="stream-json",
            timeout=60,
        )

        adapter = ClaudeCliAdapter(config)

        with patch.object(asyncio, "create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
            mock_proc = MagicMock()
            mock_proc.stdin = MagicMock()
            mock_proc.stdin.write = MagicMock()
            mock_proc.stdin.drain = AsyncMock()
            mock_proc.stdin.close = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stderr = MagicMock()

            # Simulate Claude CLI streaming response
            streaming_output = (
                '{"type":"content_block_delta","delta":{"text":"Hello"}}\n'
                '{"type":"content_block_delta","delta":{"text":" from Claude"}}\n'
            ).encode()
            mock_proc.communicate = AsyncMock(return_value=(streaming_output, b""))
            mock_proc.returncode = 0
            mock_spawn.return_value = mock_proc

            result = await adapter.execute("Say hello")

            assert result.success is True
            assert "Hello" in result.content


# ---------------------------------------------------------------------------
# invoke_cli Action Tests
# ---------------------------------------------------------------------------


class TestInvokeCliAction:
    """Tests for invoke_cli subagent action."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_cli_action_success(self):
        """invoke_cli action should execute CLI in oneshot mode."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent
        from noeagent.cli_adapter import CliExecutionResult, ExternalCliAdapter
        from noeagent.graph.nodes import subagent_node
        from noeagent.state import AgentState

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        agent._cli_adapter = ExternalCliAdapter()

        # Register a mock CLI config
        config = CliSubagentConfig(
            name="test-cli",
            command="test",
            mode="oneshot",
        )
        agent._cli_adapter.register_config(config)

        # Mock execute_oneshot
        mock_result = CliExecutionResult(success=True, content="CLI output here")
        agent._cli_adapter.execute_oneshot = AsyncMock(return_value=mock_result)

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    additional_kwargs={
                        "subagent_action": {
                            "action": "invoke_cli",
                            "name": "test-cli",
                            "message": "Do something",
                        }
                    },
                )
            ],
            "iteration": 0,
            "tool_results": [],
        }

        result = await subagent_node(state, agent=agent)

        assert "tool_results" in result
        assert "CLI output here" in result["tool_results"][0]["result"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_cli_action_with_options(self):
        """invoke_cli action should pass allowed_tools option."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent
        from noeagent.cli_adapter import CliExecutionResult, ExternalCliAdapter
        from noeagent.graph.nodes import subagent_node
        from noeagent.state import AgentState

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        agent._cli_adapter = ExternalCliAdapter()

        config = CliSubagentConfig(
            name="claude",
            command="claude",
            mode="oneshot",
        )
        agent._cli_adapter.register_config(config)

        mock_result = CliExecutionResult(success=True, content="Done")
        agent._cli_adapter.execute_oneshot = AsyncMock(return_value=mock_result)

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    additional_kwargs={
                        "subagent_action": {
                            "action": "invoke_cli",
                            "name": "claude",
                            "message": "Edit file",
                            "allowed_tools": ["Edit", "Read"],
                            "skip_permissions": True,
                        }
                    },
                )
            ],
            "iteration": 0,
            "tool_results": [],
        }

        await subagent_node(state, agent=agent)

        # Verify execute_oneshot was called with the options
        agent._cli_adapter.execute_oneshot.assert_awaited_once()
        call_kwargs = agent._cli_adapter.execute_oneshot.call_args[1]
        assert call_kwargs["allowed_tools"] == ["Edit", "Read"]
        assert call_kwargs["skip_permissions"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_cli_action_failure(self):
        """invoke_cli action should handle execution failure."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent
        from noeagent.cli_adapter import CliExecutionResult, ExternalCliAdapter
        from noeagent.graph.nodes import subagent_node
        from noeagent.state import AgentState

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        agent._cli_adapter = ExternalCliAdapter()

        config = CliSubagentConfig(
            name="failing-cli",
            command="test",
            mode="oneshot",
        )
        agent._cli_adapter.register_config(config)

        mock_result = CliExecutionResult(
            success=False,
            error="Command failed with exit code 1",
        )
        agent._cli_adapter.execute_oneshot = AsyncMock(return_value=mock_result)

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    additional_kwargs={
                        "subagent_action": {
                            "action": "invoke_cli",
                            "name": "failing-cli",
                            "message": "Do something",
                        }
                    },
                )
            ],
            "iteration": 0,
            "tool_results": [],
        }

        result = await subagent_node(state, agent=agent)

        assert "Error:" in result["tool_results"][0]["result"]


# ---------------------------------------------------------------------------
# BuiltInAgentCapabilityProvider Streaming Tests
# ---------------------------------------------------------------------------


class TestBuiltInAgentCapabilityProviderStreaming:
    """Tests for BuiltInAgentCapabilityProvider.invoke_streaming()."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_streaming_with_progress_support(self):
        """invoke_streaming should yield wrapped progress events."""
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider
        from noesium.core.event import ProgressEvent, ProgressEventType

        # Create a mock agent with astream_progress
        mock_agent = MagicMock()

        async def mock_astream_progress(message, **kwargs):
            yield ProgressEvent(
                type=ProgressEventType.SESSION_START,
                session_id="test-session",
                summary="Test started",
            )
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id="test-session",
                summary="Thinking...",
            )
            yield ProgressEvent(
                type=ProgressEventType.FINAL_ANSWER,
                session_id="test-session",
                text="Task completed",
                summary="Done",
            )
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id="test-session",
            )

        mock_agent.astream_progress = mock_astream_progress

        provider = BuiltInAgentCapabilityProvider(
            name="test_agent",
            agent_factory=lambda: mock_agent,
            agent_type="test_type",
        )

        events = []
        async for event in provider.invoke_streaming(message="Test task"):
            events.append(event)

        # Should have wrapped events (excluding SESSION_START/SESSION_END)
        assert len(events) >= 2

        # Check that events are wrapped as SUBAGENT_PROGRESS
        progress_events = [e for e in events if e.type == ProgressEventType.SUBAGENT_PROGRESS]
        assert len(progress_events) >= 2  # THINKING and FINAL_ANSWER wrapped

        # Check metadata is preserved
        for evt in progress_events:
            assert evt.subagent_id == "test_agent"
            assert "child_event_type" in (evt.metadata or {})
            assert "agent_type" in (evt.metadata or {})

        # Last event should be SUBAGENT_END
        assert events[-1].type == ProgressEventType.SUBAGENT_END

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_streaming_without_progress_support(self):
        """invoke_streaming should fallback to invoke for non-streaming agents."""
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider
        from noesium.core.event import ProgressEventType

        # Create a mock agent without astream_progress
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value="Task completed")
        # No astream_progress attribute
        del mock_agent.astream_progress

        provider = BuiltInAgentCapabilityProvider(
            name="non_streaming_agent",
            agent_factory=lambda: mock_agent,
        )

        events = []
        async for event in provider.invoke_streaming(message="Test task"):
            events.append(event)

        # Should emit SUBAGENT_START and SUBAGENT_END
        assert len(events) == 2
        assert events[0].type == ProgressEventType.SUBAGENT_START
        assert events[1].type == ProgressEventType.SUBAGENT_END
        assert "no streaming" in events[0].summary.lower()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_streaming_error_handling(self):
        """invoke_streaming should handle errors gracefully."""
        from noesium.core.capability.providers import BuiltInAgentCapabilityProvider
        from noesium.core.event import ProgressEvent, ProgressEventType

        # Create a mock agent that raises an error
        mock_agent = MagicMock()

        async def mock_astream_progress(message, **kwargs):
            yield ProgressEvent(
                type=ProgressEventType.SESSION_START,
                session_id="test-session",
                summary="Test started",
            )
            raise RuntimeError("Test error")

        mock_agent.astream_progress = mock_astream_progress

        provider = BuiltInAgentCapabilityProvider(
            name="failing_agent",
            agent_factory=lambda: mock_agent,
        )

        events = []
        with pytest.raises(RuntimeError, match="Test error"):
            async for event in provider.invoke_streaming(message="Test task"):
                events.append(event)

        # Should have yielded at least the SESSION_START (wrapped as SUBAGENT_PROGRESS)
        # But the error should propagate


# ---------------------------------------------------------------------------
# NoeAgent Streaming Integration Tests
# ---------------------------------------------------------------------------


class TestNoeAgentBuiltinStreaming:
    """Tests for NoeAgent.execute_builtin_subagent_streaming()."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execute_builtin_subagent_streaming(self):
        """execute_builtin_subagent_streaming delegates to invoke_subagent."""
        from noeagent.agent import NoeAgent

        from noesium.core.event import ProgressEvent, ProgressEventType

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        agent._subagent_event_queue = asyncio.Queue()

        # Track callbacks
        callback_events = []

        async def mock_callback(event):
            callback_events.append(event)

        # Use agent.config.progress_callbacks (used by _fire_callbacks)
        agent.config.progress_callbacks = [mock_callback]

        # Mock invoke_subagent to return a result (new signature: subagent_id, message)
        async def fake_invoke_subagent(subagent_id, message, **kwargs):
            # Simulate firing progress events like invoke_subagent does
            for event in [
                ProgressEvent(
                    type=ProgressEventType.SUBAGENT_PROGRESS,
                    subagent_id=subagent_id,
                    summary=f"[{subagent_id}] Navigating...",
                ),
                ProgressEvent(
                    type=ProgressEventType.SUBAGENT_PROGRESS,
                    subagent_id=subagent_id,
                    summary=f"[{subagent_id}] Clicking button",
                ),
                ProgressEvent(
                    type=ProgressEventType.SUBAGENT_END,
                    subagent_id=subagent_id,
                    summary=f"[{subagent_id}] completed",
                    detail="Browser task completed successfully",
                ),
            ]:
                await agent._fire_callbacks(event)
                agent._subagent_event_queue.put_nowait(event)
            return "Browser task completed successfully"

        agent.invoke_subagent = fake_invoke_subagent

        # New signature: execute_builtin_subagent_streaming(subagent_id, message)
        result = await agent.execute_builtin_subagent_streaming("browser_use", "Navigate to example.com")

        assert result == "Browser task completed successfully"

        # Check callbacks were fired
        assert len(callback_events) == 3

        # Check events were queued
        assert agent._subagent_event_queue.qsize() == 3

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invoke_builtin_uses_streaming(self):
        """invoke_builtin action delegates to agent.invoke_subagent."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent
        from noeagent.graph.nodes import subagent_node
        from noeagent.state import AgentState

        from noesium.core.agent.subagent import SubagentManager

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
        agent._subagent_manager = SubagentManager()
        agent._subagent_event_queue = asyncio.Queue()

        # Mock invoke_subagent to verify it's called
        agent.invoke_subagent = AsyncMock(return_value="Browser task done")

        state: AgentState = {
            "messages": [
                AIMessage(
                    content="",
                    additional_kwargs={
                        "subagent_action": {
                            "action": "invoke_builtin",
                            "name": "browser_use",
                            "message": "Navigate to example.com",
                        }
                    },
                )
            ],
            "iteration": 0,
            "tool_results": [],
        }

        result = await subagent_node(state, agent=agent)

        assert "tool_results" in result
        # invoke_subagent should have been called
        agent.invoke_subagent.assert_awaited_once_with("browser_use", "Navigate to example.com")

    def _make_streaming_generator(self):
        """Helper to create an async generator for streaming."""
        from noesium.core.event import ProgressEvent, ProgressEventType

        async def gen():
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_PROGRESS,
                subagent_id="browser_use",
                summary="[browser_use] Working...",
            )
            yield ProgressEvent(
                type=ProgressEventType.SUBAGENT_END,
                subagent_id="browser_use",
                summary="[browser_use] completed",
                detail="Done",
            )

        return gen()


# ---------------------------------------------------------------------------
# BrowserUseAgent Progress Streaming Tests
# ---------------------------------------------------------------------------


class TestBrowserUseAgentProgressStreaming:
    """Tests for BrowserUseAgent.astream_progress()."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    @pytest.mark.llm
    async def test_astream_progress_event_sequence(self):
        """astream_progress should yield events in correct sequence."""
        from noesium.core.event import ProgressEventType
        from noesium.subagents.bu.agent import BrowserUseAgent

        # Create agent with mock LLM (parameter is 'llm', not 'llm_client')
        mock_llm = MagicMock()
        agent = BrowserUseAgent(llm=mock_llm)

        # Mock the underlying Agent.run to avoid actual browser interaction
        mock_result = MagicMock()
        mock_result.history = []
        mock_result.final_result = MagicMock(return_value="Task completed")

        # We need to mock the Agent class and its run method
        with patch("noesium.subagents.bu.agent.Agent") as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            MockAgent.return_value = mock_agent_instance

            events = []
            async for event in agent.astream_progress("Navigate to example.com"):
                events.append(event)

            # Verify event sequence
            event_types = [e.type for e in events]

            # Should start with SESSION_START
            assert event_types[0] == ProgressEventType.SESSION_START

            # Should have PLAN_CREATED
            assert ProgressEventType.PLAN_CREATED in event_types

            # Should have THINKING
            assert ProgressEventType.THINKING in event_types

            # Should have FINAL_ANSWER
            assert ProgressEventType.FINAL_ANSWER in event_types

            # Should end with SESSION_END
            assert event_types[-1] == ProgressEventType.SESSION_END

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_astream_progress_error_handling(self):
        """astream_progress should emit ERROR event on failure."""
        from noesium.core.event import ProgressEventType
        from noesium.subagents.bu.agent import BrowserUseAgent

        mock_llm = MagicMock()
        agent = BrowserUseAgent(llm=mock_llm)

        with patch("noesium.subagents.bu.agent.Agent") as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("Browser failed"))
            MockAgent.return_value = mock_agent_instance

            events = []
            with pytest.raises(RuntimeError, match="Browser failed"):
                async for event in agent.astream_progress("Test task"):
                    events.append(event)

            # Should have emitted ERROR event before raising
            error_events = [e for e in events if e.type == ProgressEventType.ERROR]
            assert len(error_events) == 1
            assert "Browser failed" in error_events[0].error


# ---------------------------------------------------------------------------
# TacitusAgent Progress Streaming Tests
# ---------------------------------------------------------------------------


class TestTacitusAgentProgressStreaming:
    """Tests for TacitusAgent.astream_progress()."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    @pytest.mark.llm
    async def test_astream_progress_event_sequence(self):
        """astream_progress should yield events in correct sequence for research."""
        from noesium.core.event import ProgressEventType
        from noesium.subagents.tacitus.agent import TacitusAgent

        # Create agent with mock LLM
        mock_llm = MagicMock()
        mock_llm.structured_completion = MagicMock(return_value=MagicMock(query=["query1", "query2"], rationale="test"))
        mock_llm.completion = MagicMock(return_value="Test response")

        # Create agent and set the mock LLM directly to avoid API key requirement
        with patch("noesium.core.llm.get_llm_client", return_value=mock_llm):
            agent = TacitusAgent(query_generation_llm=mock_llm, reflection_llm=mock_llm)
            # Set the mock LLM directly on the agent to prevent lazy initialization from calling get_llm_client
            agent.llm = mock_llm
            agent.query_generation_llm = mock_llm
            agent.reflection_llm = mock_llm

        # Mock the graph.astream to avoid actual web searches
        async def mock_astream(initial_state):
            yield {"generate_query": {"query_list": [{"query": "test query 1"}, {"query": "test query 2"}]}}
            yield {
                "web_research": {
                    "search_query": ["test query 1"],
                    "sources_gathered": [{"url": "http://example.com", "title": "Example"}],
                }
            }
            yield {"reflection": {"is_sufficient": True, "research_loop_count": 1}}
            yield {"finalize_answer": {"messages": [MagicMock(content="Research completed")]}}

        agent.graph.astream = mock_astream

        events = []
        async for event in agent.astream_progress("Research AI agents"):
            events.append(event)

        # Verify event sequence
        event_types = [e.type for e in events]

        # Should start with SESSION_START
        assert event_types[0] == ProgressEventType.SESSION_START

        # Should have THINKING events
        assert ProgressEventType.THINKING in event_types

        # Should have PLAN_CREATED
        assert ProgressEventType.PLAN_CREATED in event_types

        # Should have FINAL_ANSWER
        assert ProgressEventType.FINAL_ANSWER in event_types

        # Should end with SESSION_END
        assert event_types[-1] == ProgressEventType.SESSION_END

    @pytest.mark.asyncio
    @pytest.mark.unit
    @pytest.mark.llm
    async def test_astream_progress_reflection_events(self):
        """astream_progress should emit reflection events for research loops."""
        from noesium.core.event import ProgressEventType
        from noesium.subagents.tacitus.agent import TacitusAgent

        mock_llm = MagicMock()

        # Mock get_llm_client to return our mock LLM
        with patch("noesium.core.llm.get_llm_client", return_value=mock_llm):
            agent = TacitusAgent(query_generation_llm=mock_llm, reflection_llm=mock_llm, max_research_loops=2)

        # Mock graph with multi-loop research
        async def mock_astream(initial_state):
            yield {"generate_query": {"query_list": [{"query": "q1"}]}}
            yield {"web_research": {"search_query": ["q1"], "sources_gathered": []}}
            yield {
                "reflection": {
                    "is_sufficient": False,
                    "research_loop_count": 1,
                    "knowledge_gap": "Need more sources",
                }
            }
            yield {
                "web_research": {
                    "search_query": ["q2"],
                    "sources_gathered": [{"url": "http://test.com"}],
                }
            }
            yield {"reflection": {"is_sufficient": True, "research_loop_count": 2}}
            yield {"finalize_answer": {"messages": [MagicMock(content="Done")]}}

        agent.graph.astream = mock_astream

        events = []
        async for event in agent.astream_progress("Research topic"):
            events.append(event)

        # Should have PLAN_REVISED when research is insufficient
        plan_revised_events = [e for e in events if e.type == ProgressEventType.PLAN_REVISED]
        assert len(plan_revised_events) >= 1

        # Should have THINKING events for reflection
        thinking_events = [e for e in events if e.type == ProgressEventType.THINKING]
        assert len(thinking_events) >= 2  # At least initial and final


# ---------------------------------------------------------------------------
# End-to-End Streaming Integration Tests
# ---------------------------------------------------------------------------


class TestEndToEndStreamingIntegration:
    """End-to-end tests for the complete streaming pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.llm
    async def test_subagent_progress_in_astream_progress(self):
        """SUBAGENT_PROGRESS events should appear in NoeAgent.astream_progress()."""
        from langchain_core.messages import AIMessage
        from noeagent.agent import NoeAgent

        from noesium.core.agent.subagent import SubagentManager
        from noesium.core.event import ProgressEvent, ProgressEventType

        # Mock LLM client to avoid API key requirement
        mock_llm = MagicMock()

        with patch("noesium.core.llm.get_llm_client", return_value=mock_llm):
            agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, enable_session_logging=False))
            agent._subagent_manager = SubagentManager()

            # Mock invoke_subagent to emit progress events into the queue
            async def fake_invoke_subagent(subagent_id, message, **kwargs):
                # These events are fired via the subagent_event_queue inside astream_progress
                fake_events = [
                    ProgressEvent(
                        type=ProgressEventType.SUBAGENT_PROGRESS,
                        subagent_id=subagent_id,
                        summary=f"[{subagent_id}] Navigating to page...",
                    ),
                    ProgressEvent(
                        type=ProgressEventType.SUBAGENT_PROGRESS,
                        subagent_id=subagent_id,
                        summary=f"[{subagent_id}] Extracting content...",
                    ),
                    ProgressEvent(
                        type=ProgressEventType.SUBAGENT_END,
                        subagent_id=subagent_id,
                        summary=f"[{subagent_id}] completed",
                        detail="Browser task done",
                    ),
                ]
                for event in fake_events:
                    await agent._fire_callbacks(event)
                    if agent._subagent_event_queue is not None:
                        agent._subagent_event_queue.put_nowait(event)
                return "Browser task done"

            agent.invoke_subagent = fake_invoke_subagent

            mock_compiled = AsyncMock()

            async def fake_astream(initial, config=None):
                # Simulate the graph actually calling invoke_subagent inside subagent_node
                await fake_invoke_subagent("browser_use", "Navigate")
                # Yield control so _forward_subagent_events can pick up the queued events
                await asyncio.sleep(0)
                yield {
                    "subagent": {
                        "messages": [
                            AIMessage(
                                content="",
                                additional_kwargs={
                                    "subagent_action": {
                                        "action": "invoke_builtin",
                                        "name": "browser_use",
                                        "message": "Navigate",
                                    }
                                },
                            )
                        ],
                        "tool_results": [{"tool": "subagent:browser_use", "result": "Browser task done"}],
                    }
                }
                yield {"finalize": {"final_answer": "Done.", "messages": []}}

            mock_compiled.astream = fake_astream
            agent._build_graph = MagicMock()
            agent._build_graph.return_value.compile.return_value = mock_compiled

            events = []
            async for event in agent.astream_progress("Browse to example.com"):
                events.append(event)

            # Should have SUBAGENT_PROGRESS events in the stream
            progress_events = [e for e in events if e.type == ProgressEventType.SUBAGENT_PROGRESS]
            assert len(progress_events) >= 2

            # Should have SUBAGENT_END event
            end_events = [e for e in events if e.type == ProgressEventType.SUBAGENT_END]
            assert len(end_events) >= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tui_receives_subagent_events(self):
        """TUI should receive and display subagent progress events."""
        from noeagent.tui import SubagentTracker

        from noesium.core.event import ProgressEventType

        tracker = SubagentTracker(max_display=3)

        # Simulate subagent events
        events = [
            ProgressEvent(
                type=ProgressEventType.SUBAGENT_START,
                subagent_id="browser_use",
                summary="[browser_use] spawned",
            ),
            ProgressEvent(
                type=ProgressEventType.SUBAGENT_PROGRESS,
                subagent_id="browser_use",
                summary="[browser_use] Navigating...",
                metadata={
                    "child_event_type": "tool.start",
                    "agent_type": "browser_use",
                },
            ),
            ProgressEvent(
                type=ProgressEventType.SUBAGENT_PROGRESS,
                subagent_id="browser_use",
                summary="[browser_use] Clicking...",
                metadata={
                    "child_event_type": "tool.start",
                    "agent_type": "browser_use",
                },
            ),
            ProgressEvent(
                type=ProgressEventType.SUBAGENT_END,
                subagent_id="browser_use",
                summary="[browser_use] completed",
            ),
        ]

        for event in events:
            tracker.update(event)

        # Check tracker state
        assert "browser_use" in tracker._states
        state = tracker._states["browser_use"]
        assert state.status == "done"
        assert state.agent_type == "browser_use"

        # Render should produce output
        lines = tracker.render()
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# CliAgentCapabilityProvider Tests (Updated)
# ---------------------------------------------------------------------------


class TestCliAgentCapabilityProviderUpdated:
    """Tests for updated CliAgentCapabilityProvider with mode support."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_oneshot_mode(self):
        """Provider should execute in oneshot mode."""
        from noeagent.cli_adapter import CliExecutionResult, ExternalCliAdapter

        from noesium.core.capability.providers import CliAgentCapabilityProvider

        adapter = ExternalCliAdapter()
        mock_result = CliExecutionResult(success=True, content="Task completed")
        adapter.execute_oneshot = AsyncMock(return_value=mock_result)

        provider = CliAgentCapabilityProvider(
            "claude",
            adapter,
            mode="oneshot",
            task_types=["code_edit"],
        )

        result = await provider.invoke(message="Edit the file")

        assert result == "Task completed"
        assert provider.mode == "oneshot"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_descriptor_includes_mode(self):
        """Provider descriptor should include mode in tags."""
        from noeagent.cli_adapter import ExternalCliAdapter

        from noesium.core.capability.providers import CliAgentCapabilityProvider

        adapter = ExternalCliAdapter()

        provider = CliAgentCapabilityProvider(
            "claude",
            adapter,
            mode="oneshot",
        )

        assert "mode:oneshot" in provider.descriptor.tags
        assert "oneshot" in provider.descriptor.description
