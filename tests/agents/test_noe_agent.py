"""Comprehensive tests for the NoeAgent evolution.

Covers:
- AgentAction / ToolCallAction / SubagentAction schema parsing
- execute_step_node structured tool calling (uses CapabilityRegistry)
- subagent_node spawn and interaction
- Todo persistence via memory manager
- Config defaults and ask-mode overrides
- Routing logic
- Rich TUI rendering (plan table, tool panel, slash commands)
- Event streaming protocol
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from noesium.core.capability.models import CapabilityDescriptor, CapabilityType
from noesium.noeagent.config import NoeConfig, NoeMode
from noesium.noeagent.schemas import AgentAction, SubagentAction, ToolCallAction
from noesium.noeagent.state import AgentState, TaskPlan, TaskStep

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestAgentActionSchema:
    def test_tool_calls_parsing(self):
        action = AgentAction(
            thought="Need to search",
            tool_calls=[
                ToolCallAction(tool_name="run_bash", arguments={"command": "ls"}),
                ToolCallAction(tool_name="read_file", arguments={"file_path": "a.txt"}),
            ],
        )
        assert len(action.tool_calls) == 2
        assert action.tool_calls[0].tool_name == "run_bash"
        assert action.tool_calls[0].arguments == {"command": "ls"}
        assert action.text_response is None
        assert action.subagent is None

    def test_text_response_parsing(self):
        action = AgentAction(
            thought="I know the answer",
            text_response="42 is the answer.",
        )
        assert action.text_response == "42 is the answer."
        assert action.tool_calls is None
        assert action.subagent is None

    def test_subagent_parsing(self):
        action = AgentAction(
            thought="Delegate this subtask",
            subagent=SubagentAction(
                action="spawn",
                name="researcher",
                message="Find papers on AI",
                mode="agent",
            ),
        )
        assert action.subagent.action == "spawn"
        assert action.subagent.name == "researcher"

    def test_mark_step_complete(self):
        action = AgentAction(
            thought="Step done",
            text_response="Done.",
            mark_step_complete=True,
        )
        assert action.mark_step_complete is True

    def test_serialization_roundtrip(self):
        original = AgentAction(
            thought="test",
            tool_calls=[ToolCallAction(tool_name="run_bash", arguments={"command": "pwd"})],
            mark_step_complete=False,
        )
        data = original.model_dump()
        restored = AgentAction(**data)
        assert restored.thought == original.thought
        assert len(restored.tool_calls) == 1
        assert restored.tool_calls[0].tool_name == "run_bash"


# ---------------------------------------------------------------------------
# Rich TUI rendering tests
# ---------------------------------------------------------------------------


class TestRichTUIRendering:
    def test_render_plan_table(self):
        from noesium.noeagent.tui import render_plan_table

        plan = TaskPlan(
            goal="Test goal",
            steps=[
                TaskStep(description="Step 1", status="completed"),
                TaskStep(description="Step 2", status="in_progress"),
                TaskStep(description="Step 3", status="pending"),
                TaskStep(description="Step 4", status="failed"),
            ],
        )
        table = render_plan_table(plan)
        assert table.title == "Plan: Test goal"
        assert table.row_count == 4

    def test_render_plan_tree(self):
        from rich.tree import Tree as RichTree

        from noesium.noeagent.tui import render_plan_tree

        plan = TaskPlan(
            goal="Test goal",
            steps=[
                TaskStep(description="Step 1", status="completed"),
                TaskStep(description="Step 2", status="in_progress"),
                TaskStep(description="Step 3", status="pending"),
            ],
        )
        tree = render_plan_tree(plan)
        assert isinstance(tree, RichTree)
        assert "Plan: Test goal" in str(tree.label)
        assert tree.children is not None
        assert len(tree.children) == 3
        # Custom title
        tree2 = render_plan_tree(plan, title="[sub] Plan: custom")
        assert "[sub] Plan: custom" in str(tree2.label)

    def test_activity_line_tool_start(self):
        from noesium.core.event import ProgressEvent, ProgressEventType
        from noesium.noeagent.tui import _activity_line

        evt = ProgressEvent(
            type=ProgressEventType.TOOL_START,
            tool_name="run_bash",
            summary='Using run_bash(command="ls")',
        )
        line = _activity_line(evt)
        assert line is not None
        assert "run_bash" in line.plain

    def test_activity_line_tool_end(self):
        from noesium.core.event import ProgressEvent, ProgressEventType
        from noesium.noeagent.tui import _activity_line

        evt = ProgressEvent(
            type=ProgressEventType.TOOL_END,
            tool_name="run_bash",
            tool_result="file1.txt file2.txt",
        )
        line = _activity_line(evt)
        assert line is not None
        assert "run_bash" in line.plain

    def test_activity_line_subagent_start(self):
        from noesium.core.event import ProgressEvent, ProgressEventType
        from noesium.noeagent.tui import _activity_line

        evt = ProgressEvent(
            type=ProgressEventType.SUBAGENT_START,
            subagent_id="browser_use-1",
            summary="[browser_use-1] searching for patterns",
        )
        line = _activity_line(evt)
        assert line is not None
        # Display name "BrowserUse" should appear, with numeric suffix "-1"
        assert "BrowserUse-1" in line.plain

    def test_render_compact_progress(self):
        from noesium.noeagent.tui import render_compact_progress

        plan = TaskPlan(
            goal="Test goal",
            steps=[
                TaskStep(description="Step 1", status="completed"),
                TaskStep(description="Step 2", status="in_progress"),
                TaskStep(description="Step 3", status="pending"),
            ],
        )
        # Test with completed steps
        line = render_compact_progress(plan, "Step 2")
        assert "1/3" in line.plain
        assert "Step 2" in line.plain

        # Test without current step
        line = render_compact_progress(plan)
        assert "1/3" in line.plain

        # Test with no plan
        line = render_compact_progress(None)
        assert line.plain == ""

    def test_dynamic_thinking_text(self):
        from noesium.noeagent.tui import DynamicThinkingText

        t = DynamicThinkingText()
        # Default phase
        assert "Thinking" in t.get_text()

        # Planning phase
        t.set_phase("planning")
        text = t.get_text()
        assert any(msg in text for msg in ["Planning", "Breaking", "Creating", "Analyzing"])

        # With context
        t.set_phase("executing", "step 1")
        text = t.get_text()
        assert "step 1" in text


class TestSlashCommands:
    def test_exit_command(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/exit", agent, console) is True

    def test_quit_command(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/quit", agent, console) is True

    def test_help_command(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/help", agent, console) is False

    def test_mode_switch_to_ask(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        agent.config = NoeConfig(mode=NoeMode.AGENT)
        assert handle_slash_command("/mode ask", agent, console) is False
        assert agent.config.mode == NoeMode.ASK

    def test_mode_switch_to_agent(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        agent.config = NoeConfig(mode=NoeMode.ASK)
        assert handle_slash_command("/mode agent", agent, console) is False
        assert agent.config.mode == NoeMode.AGENT

    def test_mode_switch_invalid(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/mode unknown", agent, console) is False

    def test_plan_command_no_plan(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/plan", agent, console, current_plan=None) is False

    def test_plan_command_with_plan(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        plan = TaskPlan(goal="Test", steps=[TaskStep(description="Do thing")])
        assert handle_slash_command("/plan", agent, console, current_plan=plan) is False

    def test_clear_command(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/clear", agent, console) is False

    def test_unknown_command(self):
        from unittest.mock import MagicMock

        from rich.console import Console

        from noesium.noeagent.tui import handle_slash_command

        console = Console(file=MagicMock())
        agent = MagicMock()
        assert handle_slash_command("/foobar", agent, console) is False


# ---------------------------------------------------------------------------
# Event streaming tests
# ---------------------------------------------------------------------------


class TestStreamEvents:
    """Tests for event streaming - require LLM API key for agent initialization."""

    @pytest.mark.integration
    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_plan_created_event(self):
        """astream_events yields plan.created when plan node emits a plan."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))
        plan = TaskPlan(
            goal="Test",
            steps=[TaskStep(description="Step 1")],
        )

        mock_compiled = AsyncMock()

        async def fake_astream(initial):
            yield {"plan": {"plan": plan, "messages": []}}

        mock_compiled.astream = fake_astream
        mock_compiled.get_state = MagicMock()

        agent.initialize = AsyncMock()
        agent._build_graph = MagicMock()
        agent._build_graph.return_value.compile.return_value = mock_compiled

        events = []
        async for ev in agent.astream_events("test"):
            events.append(ev)

        plan_events = [e for e in events if e["type"] == "plan.created"]
        assert len(plan_events) == 1
        assert plan_events[0]["plan_snapshot"] is not None
        assert plan_events[0]["plan_snapshot"]["goal"] == "Test"

    @pytest.mark.integration
    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_final_answer_event(self):
        """astream_events yields final.answer."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))

        mock_compiled = AsyncMock()

        async def fake_astream(initial):
            yield {"finalize": {"final_answer": "The answer.", "messages": []}}

        mock_compiled.astream = fake_astream

        agent.initialize = AsyncMock()
        agent._build_graph = MagicMock()
        agent._build_graph.return_value.compile.return_value = mock_compiled

        events = []
        async for ev in agent.astream_events("test"):
            events.append(ev)

        final_events = [e for e in events if e["type"] == "final.answer"]
        assert len(final_events) == 1
        assert final_events[0]["text"] == "The answer."

    @pytest.mark.integration
    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_tool_start_event(self):
        """astream_events yields tool.start from AIMessage.tool_calls."""
        from langchain_core.messages import AIMessage

        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))

        msg = AIMessage(
            content="",
            tool_calls=[{"name": "run_bash", "args": {"command": "ls"}, "id": "c1"}],
        )

        mock_compiled = AsyncMock()

        async def fake_astream(initial):
            yield {"execute_step": {"messages": [msg], "iteration": 1}}

        mock_compiled.astream = fake_astream

        agent.initialize = AsyncMock()
        agent._build_graph = MagicMock()
        agent._build_graph.return_value.compile.return_value = mock_compiled

        events = []
        async for ev in agent.astream_events("test"):
            events.append(ev)

        tc_events = [e for e in events if e["type"] == "tool.start"]
        assert len(tc_events) == 1
        assert tc_events[0]["tool_name"] == "run_bash"
        assert tc_events[0]["tool_args"] == {"command": "ls"}

    @pytest.mark.integration
    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_reflection_event(self):
        """astream_events yields reflection event."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))

        mock_compiled = AsyncMock()

        async def fake_astream(initial):
            yield {"reflect": {"reflection": "Good progress so far.", "messages": []}}

        mock_compiled.astream = fake_astream

        agent.initialize = AsyncMock()
        agent._build_graph = MagicMock()
        agent._build_graph.return_value.compile.return_value = mock_compiled

        events = []
        async for ev in agent.astream_events("test"):
            events.append(ev)

        ref_events = [e for e in events if e["type"] == "reflection"]
        assert len(ref_events) == 1
        assert ref_events[0]["text"] == "Good progress so far."

    @pytest.mark.integration
    @pytest.mark.llm
    @pytest.mark.asyncio
    async def test_session_lifecycle_events(self):
        """astream_events emits session.start at beginning and session.end at end."""
        from noesium.noeagent.agent import NoeAgent

        agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))

        mock_compiled = AsyncMock()

        async def fake_astream(initial):
            yield {"finalize": {"final_answer": "Done.", "messages": []}}

        mock_compiled.astream = fake_astream

        agent.initialize = AsyncMock()
        agent._build_graph = MagicMock()
        agent._build_graph.return_value.compile.return_value = mock_compiled

        events = []
        async for ev in agent.astream_events("test"):
            events.append(ev)

        types = [e["type"] for e in events]
        assert types[0] == "session.start"
        assert types[-1] == "session.end"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestNoeConfig:
    def test_defaults(self):
        cfg = NoeConfig()
        assert cfg.mode == NoeMode.AGENT
        assert "bash" in cfg.enabled_toolkits
        assert "python_executor" in cfg.enabled_toolkits
        assert "file_edit" in cfg.enabled_toolkits
        assert "document" in cfg.enabled_toolkits
        assert "image" in cfg.enabled_toolkits
        assert "tabular_data" in cfg.enabled_toolkits
        assert "web_search" in cfg.enabled_toolkits
        assert "user_interaction" in cfg.enabled_toolkits
        assert cfg.enable_subagents is True
        assert cfg.interface_mode == "library"
        assert cfg.load_dotenv is True
        assert cfg.tui_history_size == 1000

    def test_default_builtin_subagents(self):
        """Test that default built-in subagents are loaded."""
        cfg = NoeConfig()
        assert len(cfg.builtin) == 2

        browser_use = cfg.get_builtin_subagent("browser_use")
        assert browser_use is not None
        assert browser_use["agent_type"] == "browser_use"
        assert browser_use["enabled"] is True

        tacitus = cfg.get_builtin_subagent("tacitus")
        assert tacitus is not None
        assert tacitus["agent_type"] == "tacitus"
        assert tacitus["enabled"] is True

    def test_get_enabled_builtin_subagents(self):
        """Test filtering enabled built-in subagents."""
        cfg = NoeConfig()
        enabled = cfg.get_enabled_builtin_subagents()
        assert len(enabled) == 2
        assert all(s.enabled for s in enabled)

    def test_create_browser_use_agent_respects_headless_config(self):
        """Test headless precedence: env var > config > default."""
        from noesium.noeagent.agent import NoeAgent
        from noesium.noeagent.config import AgentSubagentConfig
        from noesium.subagents.bu.config import DEFAULT_HEADLESS

        # Save original env var state
        original_env = os.getenv("BROWSER_USE_HEADLESS")

        try:
            # Test 1: Config is used when no env var is set
            os.environ.pop("BROWSER_USE_HEADLESS", None)
            agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT))

            cfg_headed = AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Web automation",
                config={"headless": False},
            )
            bu_headed = agent._create_browser_use_agent(cfg_headed)
            assert bu_headed.browser_profile.headless is False, "Config headless=False should work"

            cfg_headless = AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Web automation",
                config={"headless": True},
            )
            bu_headless = agent._create_browser_use_agent(cfg_headless)
            assert bu_headless.browser_profile.headless is True, "Config headless=True should work"

            # Test 2: Default is used when neither env nor config is set
            cfg_default = AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Web automation",
            )
            bu_default = agent._create_browser_use_agent(cfg_default)
            assert bu_default.browser_profile.headless is DEFAULT_HEADLESS, "Default should be used"

            # Test 3: Env var overrides config (false overrides true)
            os.environ["BROWSER_USE_HEADLESS"] = "false"
            cfg_true = AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                config={"headless": True},
            )
            bu_override = agent._create_browser_use_agent(cfg_true)
            assert bu_override.browser_profile.headless is False, "Env var should override config"

            # Test 4: Env var overrides config (true overrides false)
            os.environ["BROWSER_USE_HEADLESS"] = "true"
            cfg_false = AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                config={"headless": False},
            )
            bu_override2 = agent._create_browser_use_agent(cfg_false)
            assert bu_override2.browser_profile.headless is True, "Env var should override config"

        finally:
            # Restore original env var state
            if original_env is not None:
                os.environ["BROWSER_USE_HEADLESS"] = original_env
            else:
                os.environ.pop("BROWSER_USE_HEADLESS", None)

    def test_ask_mode_overrides(self):
        cfg = NoeConfig(mode=NoeMode.ASK).effective()
        assert cfg.max_iterations == 1
        assert cfg.enabled_toolkits == []
        assert cfg.permissions == []
        assert cfg.persist_memory is False

    def test_agent_mode_no_override(self):
        cfg = NoeConfig(mode=NoeMode.AGENT).effective()
        assert cfg.max_iterations == 25
        assert len(cfg.enabled_toolkits) > 0

    def test_config_priority_env_overrides_default(self, monkeypatch):
        """Environment variables should override default values."""
        monkeypatch.setenv("NOESIUM_LLM_PROVIDER", "ollama")
        cfg = NoeConfig()
        assert cfg.llm_provider == "ollama"
        monkeypatch.delenv("NOESIUM_LLM_PROVIDER")

    def test_load_dotenv_disabled(self, tmp_path, monkeypatch):
        """Test that dotenv loading can be disabled."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR_FROM_DOTENV=from_dotenv_value")

        # Make sure the env var is not set
        monkeypatch.delenv("TEST_VAR_FROM_DOTENV", raising=False)

        cfg = NoeConfig(load_dotenv=False, dotenv_path=str(env_file))
        cfg.load_dotenv_if_enabled()
        # Should not load the env file
        assert os.getenv("TEST_VAR_FROM_DOTENV") is None

    def test_load_dotenv_custom_path(self, tmp_path, monkeypatch):
        """Test loading dotenv from custom path."""
        env_file = tmp_path / "custom.env"
        env_file.write_text("TEST_CUSTOM_DOTENV=custom_value")

        # Make sure the env var is not set
        monkeypatch.delenv("TEST_CUSTOM_DOTENV", raising=False)

        try:
            cfg = NoeConfig(load_dotenv=True, dotenv_path=str(env_file))
            cfg.load_dotenv_if_enabled()
            assert os.getenv("TEST_CUSTOM_DOTENV") == "custom_value"
        finally:
            monkeypatch.delenv("TEST_CUSTOM_DOTENV", raising=False)

    def test_tui_history_config(self):
        """Test TUI history configuration."""
        cfg = NoeConfig()
        assert cfg.tui_history_file.endswith("history.json")
        assert cfg.tui_history_size == 1000

        custom_cfg = NoeConfig(tui_history_file="/custom/path/history.json", tui_history_size=500)
        assert custom_cfg.tui_history_file == "/custom/path/history.json"
        assert custom_cfg.tui_history_size == 500


class TestInputHistory:
    def test_history_add_and_navigate(self, tmp_path):
        """Test adding to history and navigating."""
        from noesium.noeagent.tui import InputHistory

        history_file = tmp_path / "history.json"
        history = InputHistory(str(history_file))

        history.add("first command")
        history.add("second command")

        # Navigate up
        assert history.up("") == "second command"
        assert history.up("") == "first command"

        # Navigate down
        assert history.down("") == "second command"
        assert history.down("") == ""
        assert history.down("") is None

    def test_history_persistence(self, tmp_path):
        """Test that history persists across instances."""
        from noesium.noeagent.tui import InputHistory

        history_file = tmp_path / "history.json"

        history1 = InputHistory(str(history_file))
        history1.add("saved command")

        # Create new instance
        history2 = InputHistory(str(history_file))
        assert "saved command" in history2.history

    def test_history_max_size(self, tmp_path):
        """Test history respects max size."""
        from noesium.noeagent.tui import InputHistory

        history_file = tmp_path / "history.json"
        history = InputHistory(str(history_file), max_size=5)

        for i in range(10):
            history.add(f"command {i}")

        assert len(history.history) == 5
        assert history.history[0] == "command 5"
        assert history.history[-1] == "command 9"

    def test_history_no_duplicates(self, tmp_path):
        """Test that consecutive duplicates are not added."""
        from noesium.noeagent.tui import InputHistory

        history_file = tmp_path / "history.json"
        history = InputHistory(str(history_file))

        history.add("same command")
        history.add("same command")
        history.add("same command")

        assert len(history.history) == 1


# ---------------------------------------------------------------------------
# Node tests (with mocked LLM, uses CapabilityRegistry)
# ---------------------------------------------------------------------------


def _mock_registry_with_tools(tools: list[dict] | None = None):
    """Create a mock CapabilityRegistry with optional tool providers."""
    registry = MagicMock()
    providers = []
    if tools:
        for t in tools:
            p = MagicMock()
            desc = CapabilityDescriptor(
                capability_id=t["name"],
                capability_type=CapabilityType.TOOL,
                description=t.get("description", ""),
                input_schema=t.get("input_schema", {}),
            )
            type(p).descriptor = PropertyMock(return_value=desc)
            p.invoke = AsyncMock(return_value=t.get("result", "ok"))
            providers.append(p)
    registry.list_providers.return_value = providers
    registry.get_by_name = MagicMock(
        side_effect=lambda name: next((p for p in providers if p.descriptor.capability_id == name), None)
    )
    return registry


class TestExecuteStepNode:
    @pytest.mark.asyncio
    async def test_tool_call_produces_ai_message_with_tool_calls(self):
        from langchain_core.messages import AIMessage, HumanMessage

        from noesium.noeagent.nodes import execute_step_node

        mock_llm = MagicMock()
        mock_action = AgentAction(
            thought="I need to list files",
            tool_calls=[ToolCallAction(tool_name="run_bash", arguments={"command": "ls"})],
        )
        mock_llm.structured_completion = MagicMock(return_value=mock_action)

        mock_registry = _mock_registry_with_tools()

        state: AgentState = {
            "messages": [HumanMessage(content="List files in current dir")],
            "plan": TaskPlan(goal="List files", steps=[TaskStep(description="Run ls")]),
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }

        result = await execute_step_node(state, llm=mock_llm, registry=mock_registry)

        msg = result["messages"][0]
        assert isinstance(msg, AIMessage)
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "run_bash"

    @pytest.mark.asyncio
    async def test_text_response_produces_plain_ai_message(self):
        from langchain_core.messages import AIMessage, HumanMessage

        from noesium.noeagent.nodes import execute_step_node

        mock_llm = MagicMock()
        mock_action = AgentAction(
            thought="I know the answer",
            text_response="The answer is 42.",
        )
        mock_llm.structured_completion = MagicMock(return_value=mock_action)

        mock_registry = _mock_registry_with_tools()

        state: AgentState = {
            "messages": [HumanMessage(content="What is 6*7?")],
            "plan": TaskPlan(goal="Compute", steps=[TaskStep(description="Calculate")]),
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }

        result = await execute_step_node(state, llm=mock_llm, registry=mock_registry)

        msg = result["messages"][0]
        assert isinstance(msg, AIMessage)
        assert msg.content == "The answer is 42."
        assert not getattr(msg, "tool_calls", None)

    @pytest.mark.asyncio
    async def test_subagent_action_sets_additional_kwargs(self):
        from langchain_core.messages import HumanMessage

        from noesium.noeagent.nodes import execute_step_node

        mock_llm = MagicMock()
        mock_action = AgentAction(
            thought="Delegate research",
            subagent=SubagentAction(action="spawn", name="helper", message="Find data"),
        )
        mock_llm.structured_completion = MagicMock(return_value=mock_action)

        mock_registry = _mock_registry_with_tools()

        state: AgentState = {
            "messages": [HumanMessage(content="Research this")],
            "plan": TaskPlan(goal="Research", steps=[TaskStep(description="Delegate")]),
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }

        result = await execute_step_node(state, llm=mock_llm, registry=mock_registry)

        msg = result["messages"][0]
        assert msg.additional_kwargs.get("subagent_action") is not None
        assert msg.additional_kwargs["subagent_action"]["name"] == "helper"

    @pytest.mark.asyncio
    async def test_fallback_on_structured_completion_failure(self):
        from langchain_core.messages import HumanMessage

        from noesium.noeagent.nodes import execute_step_node

        mock_llm = MagicMock()
        mock_llm.structured_completion = MagicMock(side_effect=Exception("Instructor failed"))
        mock_llm.completion = MagicMock(return_value="Fallback answer")

        mock_registry = _mock_registry_with_tools()

        state: AgentState = {
            "messages": [HumanMessage(content="Question")],
            "plan": None,
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }

        result = await execute_step_node(state, llm=mock_llm, registry=mock_registry)

        msg = result["messages"][0]
        assert msg.content == "Fallback answer"


# ---------------------------------------------------------------------------
# Subagent node tests
# ---------------------------------------------------------------------------


class TestSubagentNode:
    @pytest.mark.asyncio
    async def test_spawn_subagent(self):
        from langchain_core.messages import AIMessage, HumanMessage

        from noesium.noeagent.nodes import subagent_node

        mock_agent = AsyncMock()
        mock_agent.spawn_subagent = AsyncMock(return_value="helper-1")
        mock_agent.interact_with_subagent = AsyncMock(return_value="Research results")
        mock_agent._subagents = {}

        sa_msg = AIMessage(content="Delegate")
        sa_msg.additional_kwargs["subagent_action"] = {
            "action": "spawn",
            "name": "helper",
            "message": "Find papers",
            "mode": "agent",
        }

        state: AgentState = {
            "messages": [HumanMessage(content="x"), sa_msg],
            "plan": None,
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }

        result = await subagent_node(state, agent=mock_agent)

        mock_agent.spawn_subagent.assert_awaited_once()
        mock_agent.interact_with_subagent.assert_awaited_once_with("helper-1", "Find papers")
        assert "Research results" in result["messages"][0].content


# ---------------------------------------------------------------------------
# Todo persistence tests
# ---------------------------------------------------------------------------


class TestTodoPersistence:
    @pytest.mark.asyncio
    async def test_plan_persisted_to_memory(self):
        from noesium.noeagent.nodes import _persist_plan_to_memory

        plan = TaskPlan(
            goal="Test",
            steps=[TaskStep(description="Step 1", status="completed")],
        )
        mock_mm = AsyncMock()
        await _persist_plan_to_memory(plan, mock_mm)

        mock_mm.store.assert_awaited_once()
        call_kwargs = mock_mm.store.call_args
        assert call_kwargs.kwargs["key"] == "current_plan"
        assert "Step 1" in call_kwargs.kwargs["value"]

    @pytest.mark.asyncio
    async def test_plan_persist_skips_when_no_memory(self):
        from noesium.noeagent.nodes import _persist_plan_to_memory

        plan = TaskPlan(goal="x", steps=[TaskStep(description="y")])
        await _persist_plan_to_memory(plan, None)


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


class TestRouting:
    """Tests for routing logic - require LLM API key for agent initialization."""

    def _make_agent(self):
        from noesium.noeagent.agent import NoeAgent

        return NoeAgent(NoeConfig(mode=NoeMode.AGENT))

    @pytest.mark.integration
    @pytest.mark.llm
    def test_route_finalize_when_plan_complete(self):
        agent = self._make_agent()
        plan = TaskPlan(goal="x", steps=[], is_complete=True)
        state: AgentState = {
            "messages": [],
            "plan": plan,
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }
        assert agent._route_after_execute(state) == "finalize"

    @pytest.mark.integration
    @pytest.mark.llm
    def test_route_tool_node_when_tool_calls(self):
        from langchain_core.messages import AIMessage

        agent = self._make_agent()
        msg = AIMessage(
            content="test",
            tool_calls=[{"name": "run_bash", "args": {}, "id": "c1"}],
        )
        state: AgentState = {
            "messages": [msg],
            "plan": TaskPlan(goal="x", steps=[TaskStep(description="y")]),
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }
        assert agent._route_after_execute(state) == "tool_node"

    @pytest.mark.integration
    @pytest.mark.llm
    def test_route_subagent_when_subagent_action(self):
        from langchain_core.messages import AIMessage

        agent = self._make_agent()
        msg = AIMessage(content="delegate")
        msg.additional_kwargs["subagent_action"] = {"action": "spawn", "name": "x"}
        state: AgentState = {
            "messages": [msg],
            "plan": TaskPlan(goal="x", steps=[TaskStep(description="y")]),
            "iteration": 0,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }
        assert agent._route_after_execute(state) == "subagent_node"

    @pytest.mark.integration
    @pytest.mark.llm
    def test_route_reflect_at_interval(self):
        from langchain_core.messages import AIMessage

        agent = self._make_agent()
        msg = AIMessage(content="done")
        state: AgentState = {
            "messages": [msg],
            "plan": TaskPlan(goal="x", steps=[TaskStep(description="y")]),
            "iteration": 3,
            "tool_results": [],
            "reflection": "",
            "final_answer": "",
        }
        assert agent._route_after_execute(state) == "reflect"

    @pytest.mark.integration
    @pytest.mark.llm
    def test_route_after_reflect_revise(self):
        agent = self._make_agent()
        state: AgentState = {
            "messages": [],
            "plan": TaskPlan(goal="x", steps=[TaskStep(description="y")]),
            "iteration": 3,
            "tool_results": [],
            "reflection": "We need to REVISE the plan.",
            "final_answer": "",
        }
        assert agent._route_after_reflect(state) == "revise_plan"

    @pytest.mark.integration
    @pytest.mark.llm
    def test_route_after_reflect_continue(self):
        agent = self._make_agent()
        state: AgentState = {
            "messages": [],
            "plan": TaskPlan(goal="x", steps=[TaskStep(description="y")]),
            "iteration": 3,
            "tool_results": [],
            "reflection": "Progress is good, continue.",
            "final_answer": "",
        }
        assert agent._route_after_reflect(state) == "execute_step"


# ---------------------------------------------------------------------------
# Tool description builder tests (uses CapabilityRegistry)
# ---------------------------------------------------------------------------


class TestToolDescriptions:
    def test_build_tool_descriptions_with_tools(self):
        from noesium.noeagent.nodes import _build_tool_descriptions

        registry = _mock_registry_with_tools(
            [
                {
                    "name": "run_bash",
                    "description": "Execute a bash command",
                    "input_schema": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            ]
        )

        result = _build_tool_descriptions(registry)
        assert "run_bash" in result
        assert "command" in result
        assert "(required)" in result

    def test_build_tool_descriptions_empty(self):
        from noesium.noeagent.nodes import _build_tool_descriptions

        assert _build_tool_descriptions(None) == "No tools available."

        mock_registry = MagicMock()
        mock_registry.list_providers.return_value = []
        assert _build_tool_descriptions(mock_registry) == "No tools available."
