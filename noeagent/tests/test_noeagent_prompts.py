"""Tests for NoeAgent prompt loading and rendering."""

import pytest

from noeagent.prompts import get_prompt_manager


def get_test_variables(prompt_name: str) -> dict:
    """Get test variables for each prompt."""
    test_vars = {
        "ask_system": {
            "memory_context": "Test memory context with sample data",
        },
        "agent_system": {
            "plan": "Search for recent AI papers",
            "execution_hint": "Use appropriate tools",
            "completed_results": "None yet.",
            "tool_descriptions": "- web_search: Web search\n- arxiv: ArXiv search",
        },
        "planning": {
            "goal": "Find recent papers on LLM reasoning",
            "context": "Focus on papers from 2024-2025",
            "external_subagent_info": "",
            "builtin_subagent_info": "\n  **browser_use**: Web automation\n  **tacitus**: Research synthesis",
        },
        "reflection": {
            "goal": "Research AI safety",
            "plan_steps": "1. [pending] Search papers\n2. [pending] Analyze results",
            "completed_results": "- web_search: Found 10 papers",
        },
        "revise_plan": {
            "goal": "Research AI safety",
            "original_steps": "1. [pending] Search papers",
            "feedback": "Need more specific search terms",
            "completed_results": "Initial search too broad",
        },
        "finalize": {
            "goal": "Summarize AI safety research",
            "results": "- Paper 1: Safety alignment\n- Paper 2: Interpretability",
        },
    }
    return test_vars.get(prompt_name, {})


def test_all_prompts_load():
    """Test all prompts load from package resources."""
    pm = get_prompt_manager()
    prompt_names = ["ask_system", "agent_system", "planning", "reflection", "revise_plan", "finalize"]

    for name in prompt_names:
        variables = get_test_variables(name)
        result = pm.render(name, **variables)
        assert result is not None, f"Prompt '{name}' returned None"
        assert len(result) > 100, f"Prompt '{name}' is too short ({len(result)} chars)"
        assert isinstance(result, str), f"Prompt '{name}' did not return a string"


def test_required_variables_validation():
    """Test missing required variables raise errors."""
    pm = get_prompt_manager()

    # agent_system requires 4 variables
    with pytest.raises(ValueError, match="Missing required variables"):
        pm.render("agent_system")  # Missing all required variables

    with pytest.raises(ValueError, match="Missing required variables"):
        pm.render("agent_system", plan="test")  # Missing 3 required variables

    # ask_system requires memory_context
    with pytest.raises(ValueError, match="Missing required variables"):
        pm.render("ask_system")  # Missing memory_context


def test_capability_accuracy():
    """Test prompts mention actual toolkits and subagents."""
    pm = get_prompt_manager()

    # agent_system should mention toolkits
    agent_prompt = pm.render("agent_system", **get_test_variables("agent_system"))
    assert "bash" in agent_prompt, "agent_system missing 'bash' toolkit"
    assert "web_search" in agent_prompt, "agent_system missing 'web_search' toolkit"
    assert "browser_use" in agent_prompt, "agent_system missing 'browser_use' subagent"
    assert "tacitus" in agent_prompt, "agent_system missing 'tacitus' subagent"

    # Should mention execution modes
    assert "tool_calls" in agent_prompt, "agent_system missing 'tool_calls' execution mode"
    assert "subagent" in agent_prompt, "agent_system missing 'subagent' execution mode"

    # planning should mention execution modes
    planning_prompt = pm.render("planning", **get_test_variables("planning"))
    assert "tool" in planning_prompt, "planning missing 'tool' execution mode"
    assert "subagent" in planning_prompt, "planning missing 'subagent' execution mode"
    assert "external_subagent" in planning_prompt, "planning missing 'external_subagent' execution mode"
    assert "builtin_agent" in planning_prompt, "planning missing 'builtin_agent' execution mode"


def test_prompt_caching():
    """Test that prompts are cached after first load."""
    pm = get_prompt_manager()

    # First load
    result1 = pm.render("ask_system", memory_context="test")

    # Second load should use cache
    result2 = pm.render("ask_system", memory_context="test")

    assert result1 == result2

    # Clear cache
    pm.clear_cache()

    # After clearing cache, should still work
    result3 = pm.render("ask_system", memory_context="test")
    assert result3 is not None


def test_prompt_not_found():
    """Test error handling for non-existent prompts."""
    pm = get_prompt_manager()

    with pytest.raises(FileNotFoundError, match="not found"):
        pm.render("nonexistent_prompt", var1="test")


def test_prompt_rendering_with_format_engine():
    """Test that format engine properly substitutes variables."""
    pm = get_prompt_manager()

    result = pm.render(
        "ask_system",
        memory_context="Custom memory context with special content",
    )

    assert "Custom memory context with special content" in result
    assert "read-only ask mode" in result


def test_optional_variables():
    """Test prompts with optional variables work correctly."""
    pm = get_prompt_manager()

    # planning has optional variables: context, external_subagent_info, builtin_subagent_info
    result1 = pm.render(
        "planning",
        goal="Test goal",
        context="Test context",
        external_subagent_info="Test external info",
        builtin_subagent_info="Test builtin info",
    )
    assert "Test goal" in result1
    assert "Test context" in result1

    # Should also work without optional variables (they have defaults)
    result2 = pm.render("planning", goal="Test goal")
    assert "Test goal" in result2


def test_prompt_metadata_in_content():
    """Test that prompts contain expected metadata sections."""
    pm = get_prompt_manager()

    # agent_system should have sections
    agent = pm.render("agent_system", **get_test_variables("agent_system"))
    assert "# Noe" in agent or "Noe" in agent  # Should identify as Noe agent
    assert "tool" in agent.lower()  # Should mention tools

    # finalize should have synthesis instructions
    finalize = pm.render("finalize", **get_test_variables("finalize"))
    # Check for report depth guidance which is the core function
    assert "report" in finalize.lower() or "answer" in finalize.lower()


def test_all_toolkits_mentioned():
    """Test that agent_system mentions default built-in toolkits (NoeConfig.enabled_toolkits)."""
    pm = get_prompt_manager()
    agent_prompt = pm.render("agent_system", **get_test_variables("agent_system"))

    default_builtin_toolkits = [
        "bash",
        "file_edit",
        "document",
        "image",
        "python_executor",
        "tabular_data",
        "web_search",
        "user_interaction",
    ]

    for toolkit in default_builtin_toolkits:
        assert toolkit in agent_prompt, f"agent_system missing default built-in toolkit: {toolkit}"


def test_execution_modes_documented():
    """Test that all execution modes are documented in agent_system."""
    pm = get_prompt_manager()
    agent_prompt = pm.render("agent_system", **get_test_variables("agent_system"))

    execution_modes = [
        "tool",  # atomic operations
        "subagent",  # child agent delegation
        "external_subagent",  # CLI agents
        "builtin_agent",  # browser_use or tacitus
        "auto",  # context-based decision
    ]

    for mode in execution_modes:
        assert mode in agent_prompt, f"agent_system missing execution mode: {mode}"
