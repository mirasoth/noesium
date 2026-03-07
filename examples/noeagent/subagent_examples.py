#!/usr/bin/env python3
"""
NoeAgent Subagent Examples - Demonstrates three subagent types:
1. In-process child NoeAgent spawning (spawn/interact)
2. Built-in specialized agents (browser_use, tacitus)
3. External CLI subagents (oneshot and daemon modes)

Usage: uv run python examples/noeagent/subagent_examples.py
"""

import asyncio
import logging
import os

from noeagent import NoeAgent
from noeagent.config import (
    AgentSubagentConfig,
    CliSubagentConfig,
    NoeConfig,
    NoeMode,
)

# Set to false to run actual LLM calls
DEMO_MODE = os.environ.get("NOESIUM_DEMO_MODE", "true").lower() == "true"

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


# =============================================================================
# Example 1: Child Subagent Spawning
# =============================================================================


async def example_child_spawn():
    """Spawn in-process child NoeAgent subagents for task delegation."""
    print("\n[1] Child Subagent Spawning")

    if DEMO_MODE:
        print("  DEMO: spawn_subagent('researcher') -> researcher-1")
        print("  DEMO: interact_with_subagent('researcher-1', task)")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        max_iterations=5,
        enabled_toolkits=["bash"],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    subagent_id = await agent.spawn_subagent("researcher", mode=NoeMode.AGENT)
    print(f"  Spawned: {subagent_id} (depth={agent._subagents[subagent_id]._depth})")

    result = await agent.interact_with_subagent(subagent_id, "List current directory and describe files")
    print(f"  Result: {result[:100]}...")

    await agent._cleanup_subagents()


async def example_nested_subagents():
    """Demonstrate depth limits with nested subagents."""
    print("\n[1b] Nested Subagents (Depth Limits)")

    if DEMO_MODE:
        print("  Depth chain: parent(0) -> level1(1) -> level2(2) -> level3(3) -> BLOCKED")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=3,
        enable_session_logging=False,
    )

    parent = NoeAgent(config)
    await parent.initialize()

    # Build chain
    c1_id = await parent.spawn_subagent("level1")
    c1 = parent._subagents[c1_id]
    c2_id = await c1.spawn_subagent("level2")
    c2 = c1._subagents[c2_id]
    c3_id = await c2.spawn_subagent("level3")

    print(f"  Chain: {c1_id} -> {c2_id} -> {c3_id}")

    # Should fail
    try:
        await c2._subagents[c3_id].spawn_subagent("level4")
    except RuntimeError as e:
        print(f"  Blocked at depth 4: {e}")

    await parent._cleanup_subagents()


# =============================================================================
# Example 2: Built-in Specialized Agents
# =============================================================================


async def example_builtin_browser():
    """Configure browser_use subagent for web automation."""
    print("\n[2a] Built-in Browser Use Subagent")

    if DEMO_MODE:
        print("  Config: AgentSubagentConfig(name='browser_use', agent_type='browser_use')")
        print("  Tasks: web_browsing, form_filling, scraping")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation",
                enabled=True,
                task_types=["web_browsing", "form_filling", "scraping"],
                keywords=["browser", "click", "navigate", "web"],
            ),
        ],
        max_iterations=3,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()
    print("  Registered: browser_use (headless=True)")
    await agent._cleanup_subagents()


async def example_builtin_tacitus():
    """Configure tacitus research subagent."""
    print("\n[2b] Built-in Tacitus Research Subagent")

    if DEMO_MODE:
        print("  Config: AgentSubagentConfig(name='tacitus', agent_type='tacitus')")
        print("  Workflow: query -> search -> reflect -> iterate -> synthesize")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        agent_subagents=[
            AgentSubagentConfig(
                name="tacitus",
                agent_type="tacitus",
                description="Deep research agent",
                enabled=True,
                task_types=["research", "web_search", "citation"],
                keywords=["research", "search", "find", "investigate"],
            ),
        ],
        max_iterations=3,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()
    print("  Registered: tacitus (research with reflection)")
    await agent._cleanup_subagents()


# =============================================================================
# Example 3: CLI Subagent Integration
# =============================================================================


async def example_cli_oneshot():
    """CLI subagent in oneshot mode (new process per invocation)."""
    print("\n[3a] CLI Subagent - Oneshot Mode")

    if DEMO_MODE:
        print("  Config: CliSubagentConfig(name='claude', mode='oneshot', timeout=300)")
        print("  Flow: spawn -> execute -> exit")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                args=["--output-format", "stream-json"],
                mode="oneshot",
                timeout=300,
                skip_permissions=True,
                task_types=["code_edit", "code_review", "refactor"],
                allowed_tools=["Bash", "Edit", "Read", "Write"],
            ),
        ],
        max_iterations=3,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()
    print("  Configured: claude (oneshot, timeout=300s)")
    print(f"  Tools: {config.cli_subagents[0].allowed_tools}")
    await agent._cleanup_subagents()


async def example_cli_daemon():
    """CLI subagent in daemon mode (persistent process)."""
    print("\n[3b] CLI Subagent - Daemon Mode")

    if DEMO_MODE:
        print("  Config: CliSubagentConfig(mode='daemon', restart_policy='on-failure')")
        print("  Actions: spawn_cli -> interact_cli -> terminate_cli")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="persistent-agent",
                command="custom-agent-cli",
                args=["--daemon-mode"],
                mode="daemon",
                output_format="stream-json",
                timeout=600,
                restart_policy="on-failure",
                task_types=["long_running", "stateful"],
            ),
        ],
        max_iterations=3,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()
    print("  Configured: persistent-agent (daemon, restart=on-failure)")
    print("  Lifecycle: spawn -> interact -> terminate")


# =============================================================================
# Example 4: Progress Event Streaming
# =============================================================================


async def example_progress_streaming():
    """Stream progress events from subagent execution."""
    print("\n[4] Progress Event Streaming")

    if DEMO_MODE:
        print("  Events: SESSION_START -> PLAN_CREATED -> TOOL_* -> SUBAGENT_* -> FINAL_ANSWER")
        return

    events: list[str] = []

    async def callback(event):
        events.append(f"[{event.type.value}] {event.summary or ''}"[:60])

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        max_iterations=3,
        progress_callbacks=[callback],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()
    print("  Registered: progress_callbacks")
    print("  Key events: SUBAGENT_START, SUBAGENT_PROGRESS, SUBAGENT_END")
    await agent._cleanup_subagents()


# =============================================================================
# Example 5: Complete Integration
# =============================================================================


async def example_complete():
    """Full integration with all subagent types."""
    print("\n[5] Complete Integration")

    if DEMO_MODE:
        print("  Agents: browser_use, tacitus, claude")
        print("  Routing: TaskPlanner matches task -> SubagentAction")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation",
                enabled=True,
                task_types=["web_browsing", "form_filling"],
            ),
            AgentSubagentConfig(
                name="tacitus",
                agent_type="tacitus",
                description="Research agent",
                enabled=True,
                task_types=["research", "search"],
            ),
        ],
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                args=["--output-format", "stream-json"],
                mode="oneshot",
                timeout=300,
                task_types=["code_edit", "refactor"],
            ),
        ],
        enabled_toolkits=["bash", "web_search"],
        max_iterations=10,
        reflection_interval=3,
        enable_session_logging=True,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print(f"  Mode: {config.mode.value}")
    print(f"  Built-in: {[s.name for s in config.agent_subagents]}")
    print(f"  CLI: {[s.name for s in config.cli_subagents]}")
    print(f"  Toolkits: {config.enabled_toolkits}")

    await agent._cleanup_subagents()


# =============================================================================
# Entry Point
# =============================================================================


EXAMPLES = [
    example_child_spawn,
    example_nested_subagents,
    example_builtin_browser,
    example_builtin_tacitus,
    example_cli_oneshot,
    example_cli_daemon,
    example_progress_streaming,
    example_complete,
]


async def main():
    print("\nNoeAgent Subagent Examples")
    print("=" * 40)

    for example in EXAMPLES:
        await example()

    print("\n" + "=" * 40)
    print("Done. Set NOESIUM_DEMO_MODE=false for live execution.")


if __name__ == "__main__":
    asyncio.run(main())
