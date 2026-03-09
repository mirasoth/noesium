"""Tests for capability provider adapters (RFC-1004)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from noesium.core.capability.models import CapabilityProvider, CapabilityType
from noesium.core.capability.providers import (
    AgentCapabilityProvider,
    CliAgentCapabilityProvider,
    MCPCapabilityProvider,
    SkillCapabilityProvider,
    ToolCapabilityProvider,
)


def _mock_tool(name: str = "run_bash", desc: str = "Execute bash") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = desc
    tool.input_schema = {
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }
    tool.output_schema = {}
    tool.determinism_class = "stochastic"
    tool.side_effect_class = "effectful"
    tool.tags = ["shell"]
    return tool


def _mock_executor() -> MagicMock:
    executor = MagicMock()
    executor.run = AsyncMock(return_value="exec-result")
    return executor


def _mock_context() -> MagicMock:
    return MagicMock()


class TestToolCapabilityProvider:
    def test_descriptor(self):
        p = ToolCapabilityProvider(_mock_tool(), _mock_executor(), _mock_context())
        d = p.descriptor
        assert d.capability_id == "run_bash"
        assert d.capability_type == CapabilityType.TOOL
        assert d.stateful is False
        assert d.tags == ["shell"]

    @pytest.mark.asyncio
    async def test_invoke(self):
        executor = _mock_executor()
        p = ToolCapabilityProvider(_mock_tool(), executor, _mock_context())
        result = await p.invoke(command="ls")
        executor.run.assert_awaited_once()
        assert result == "exec-result"

    @pytest.mark.asyncio
    async def test_health_always_true(self):
        p = ToolCapabilityProvider(_mock_tool(), _mock_executor(), _mock_context())
        assert await p.health() is True

    def test_satisfies_protocol(self):
        p = ToolCapabilityProvider(_mock_tool(), _mock_executor(), _mock_context())
        assert isinstance(p, CapabilityProvider)

    def test_tool_property(self):
        tool = _mock_tool()
        p = ToolCapabilityProvider(tool, _mock_executor(), _mock_context())
        assert p.tool is tool


class TestMCPCapabilityProvider:
    def test_descriptor(self):
        p = MCPCapabilityProvider(_mock_tool("mcp_search"), _mock_executor(), _mock_context())
        d = p.descriptor
        assert d.capability_id == "mcp_search"
        assert d.capability_type == CapabilityType.MCP_TOOL
        assert d.stateful is False

    @pytest.mark.asyncio
    async def test_invoke(self):
        executor = _mock_executor()
        p = MCPCapabilityProvider(_mock_tool(), executor, _mock_context())
        result = await p.invoke(query="test")
        assert result == "exec-result"

    @pytest.mark.asyncio
    async def test_health_always_true(self):
        p = MCPCapabilityProvider(_mock_tool(), _mock_executor(), _mock_context())
        assert await p.health() is True


class TestSkillCapabilityProvider:
    def test_descriptor(self):
        skill = MagicMock()
        skill.name = "research_skill"
        skill.description = "Performs research"
        skill.input_schema = {}
        skill.output_schema = {}
        skill.tags = []
        p = SkillCapabilityProvider(skill, MagicMock(), MagicMock(), MagicMock())
        assert p.descriptor.capability_id == "research_skill"
        assert p.descriptor.capability_type == CapabilityType.SKILL
        assert p.descriptor.stateful is False

    @pytest.mark.asyncio
    async def test_invoke(self):
        skill = MagicMock()
        skill.name = "s"
        skill.description = "s"
        skill.input_schema = {}
        skill.output_schema = {}
        skill.execute = AsyncMock(return_value="skill-result")
        p = SkillCapabilityProvider(skill, MagicMock(), MagicMock(), MagicMock())
        result = await p.invoke(query="q")
        skill.execute.assert_awaited_once()
        assert result == "skill-result"

    @pytest.mark.asyncio
    async def test_health_always_true(self):
        skill = MagicMock()
        skill.name = "s"
        skill.description = "s"
        skill.input_schema = {}
        skill.output_schema = {}
        p = SkillCapabilityProvider(skill, MagicMock(), MagicMock(), MagicMock())
        assert await p.health() is True


class TestAgentCapabilityProvider:
    def test_descriptor_is_stateful(self):
        agent = MagicMock()
        p = AgentCapabilityProvider("helper", agent)
        d = p.descriptor
        assert d.capability_type == CapabilityType.AGENT
        assert d.stateful is True
        assert d.capability_id == "agent:helper"

    @pytest.mark.asyncio
    async def test_invoke_calls_arun(self):
        agent = MagicMock()
        agent.arun = AsyncMock(return_value="agent-result")
        p = AgentCapabilityProvider("helper", agent)
        result = await p.invoke(message="Do research")
        agent.arun.assert_awaited_once_with("Do research")
        assert result == "agent-result"

    @pytest.mark.asyncio
    async def test_health_true_when_agent_present(self):
        p = AgentCapabilityProvider("h", MagicMock())
        assert await p.health() is True

    @pytest.mark.asyncio
    async def test_health_false_when_agent_none(self):
        p = AgentCapabilityProvider("h", None)
        assert await p.health() is False

    def test_agent_property(self):
        agent = MagicMock()
        p = AgentCapabilityProvider("h", agent)
        assert p.agent is agent


class TestCliAgentCapabilityProvider:
    def test_descriptor_is_stateful(self):
        adapter = MagicMock()
        p = CliAgentCapabilityProvider("claude", adapter, task_types=["code"])
        d = p.descriptor
        assert d.capability_type == CapabilityType.CLI_AGENT
        assert d.stateful is True
        assert d.capability_id == "cli_agent:claude"
        assert "code" in d.tags

    @pytest.mark.asyncio
    async def test_invoke_calls_adapter_execute_oneshot(self):
        """Test that invoke prefers execute_oneshot when available."""
        adapter = MagicMock()
        # Mock execute_oneshot result (preferred path)
        exec_result = MagicMock()
        exec_result.success = True
        exec_result.content = "cli-result"
        adapter.execute_oneshot = AsyncMock(return_value=exec_result)
        p = CliAgentCapabilityProvider("claude", adapter)
        result = await p.invoke(message="Write code")
        adapter.execute_oneshot.assert_awaited_once_with("claude", "Write code")
        assert result == "cli-result"

    @pytest.mark.asyncio
    async def test_invoke_falls_back_to_interact(self):
        """Test that invoke falls back to interact when execute_oneshot not available."""
        adapter = MagicMock()
        # No execute_oneshot method - should fall back to interact
        del adapter.execute_oneshot
        adapter.interact = AsyncMock(return_value="cli-result")
        p = CliAgentCapabilityProvider("claude", adapter)
        result = await p.invoke(message="Write code")
        adapter.interact.assert_awaited_once_with("claude", "Write code")
        assert result == "cli-result"

    @pytest.mark.asyncio
    async def test_invoke_handles_oneshot_error(self):
        """Test that invoke handles execute_oneshot errors."""
        adapter = MagicMock()
        exec_result = MagicMock()
        exec_result.success = False
        exec_result.error = "Command failed"
        adapter.execute_oneshot = AsyncMock(return_value=exec_result)
        p = CliAgentCapabilityProvider("claude", adapter)
        result = await p.invoke(message="Write code")
        assert result == "Error: Command failed"

    @pytest.mark.asyncio
    async def test_health_delegates_to_adapter(self):
        adapter = MagicMock()
        adapter.health_check = AsyncMock(return_value=True)
        p = CliAgentCapabilityProvider("claude", adapter)
        assert await p.health() is True
        adapter.health_check.assert_awaited_once_with("claude")
