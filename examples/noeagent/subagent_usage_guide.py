#!/usr/bin/env python3
"""
NoeAgent Subagent Usage Guide - Practical patterns and best practices.

Usage: uv run python examples/noeagent/subagent_usage_guide.py
"""

import asyncio
import logging

from noesium.noeagent import NoeAgent
from noesium.noeagent.config import (
    AgentSubagentConfig,
    CliSubagentConfig,
    NoeConfig,
    NoeMode,
)
from noesium.noeagent.progress import ProgressEvent

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


# =============================================================================
# Pattern 1: Research Task Delegation
# =============================================================================


async def pattern_research_delegation():
    """Delegate focused research to a child subagent."""
    print("\n[P1] Research Task Delegation")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        enabled_toolkits=["wizsearch", "bash"],
        max_iterations=5,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    subagent_id = await agent.spawn_subagent("web-researcher", mode=NoeMode.AGENT)
    print(f"  Spawned: {subagent_id}")

    # In production:
    # result = await agent.interact_with_subagent(subagent_id, "Research Python 3.12 features")

    await agent._cleanup_subagents()


# =============================================================================
# Pattern 2: Browser Automation
# =============================================================================


async def pattern_browser_automation():
    """Use browser_use subagent for web automation."""
    print("\n[P2] Browser Automation")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        builtin=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation agent",
                enabled=True,
                task_types=["web_automation", "scraping", "form_filling"],
                keywords=["browser", "click", "navigate", "fill", "scrape"],
            ),
        ],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("  Registered: browser_use")
    print("  Routes: tasks with 'browser', 'click', 'navigate' keywords")

    await agent._cleanup_subagents()


# =============================================================================
# Pattern 3: CLI Code Assistant
# =============================================================================


async def pattern_cli_code_assistant():
    """Use CLI subagent for code editing tasks."""
    print("\n[P3] CLI Code Assistant")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        external=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                args=["--output-format", "stream-json"],
                mode="oneshot",
                timeout=300,
                skip_permissions=True,
                task_types=["code_edit", "code_review", "refactor", "debug"],
                allowed_tools=["Bash", "Edit", "Read", "Write", "Glob", "Grep"],
            ),
        ],
        enabled_toolkits=["bash"],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print(f"  Mode: oneshot (fresh process per invocation)")
    print(f"  Tools: {config.external[0].allowed_tools}")

    await agent._cleanup_subagents()


# =============================================================================
# Pattern 4: Parallel Execution
# =============================================================================


async def pattern_parallel_execution():
    """Spawn multiple subagents for parallel tasks."""
    print("\n[P4] Parallel Subagent Execution")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        enabled_toolkits=["bash"],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    # Spawn in parallel
    ids = await asyncio.gather(
        agent.spawn_subagent("analyzer", mode=NoeMode.ASK),
        agent.spawn_subagent("collector", mode=NoeMode.AGENT),
        agent.spawn_subagent("writer", mode=NoeMode.ASK),
    )

    print(f"  Spawned: {', '.join(ids)}")

    # In production:
    # results = await asyncio.gather(*[
    #     agent.interact_with_subagent(id, task) for id, task in zip(ids, tasks)
    # ])

    await agent._cleanup_subagents()


# =============================================================================
# Pattern 5: Hierarchical Delegation
# =============================================================================


async def pattern_hierarchical_delegation():
    """Hierarchical task delegation with nested subagents."""
    print("\n[P5] Hierarchical Delegation")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=3,
        enabled_toolkits=["bash"],
        enable_session_logging=False,
    )

    parent = NoeAgent(config)
    await parent.initialize()

    coord_id = await parent.spawn_subagent("coordinator")
    coord = parent._subagents[coord_id]

    w1_id = await coord.spawn_subagent("worker-1")
    w2_id = await coord.spawn_subagent("worker-2")

    print(f"  Hierarchy: parent -> {coord_id} -> [{w1_id}, {w2_id}]")
    print(f"  Max depth: {config.subagent_max_depth}")

    await parent._cleanup_subagents()


# =============================================================================
# Pattern 6: Progress Tracking
# =============================================================================


async def pattern_progress_tracking():
    """Track subagent progress with event callbacks."""
    print("\n[P6] Progress Tracking")

    async def on_progress(event: ProgressEvent):
        parts = [f"[{event.type.value}]"]
        if event.subagent_id:
            parts.append(f"subagent={event.subagent_id}")
        if event.tool_name:
            parts.append(f"tool={event.tool_name}")
        if event.summary:
            parts.append(event.summary[:40])
        print(f"  {' '.join(parts)}")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        progress_callbacks=[on_progress],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("  Key events: SUBAGENT_START, SUBAGENT_PROGRESS, SUBAGENT_END")

    await agent._cleanup_subagents()


# =============================================================================
# Pattern 7: Error Handling
# =============================================================================


async def pattern_error_handling():
    """Common error handling patterns."""
    print("\n[P7] Error Handling Patterns")

    print("""
  Depth limit exceeded:
    try:
        await agent.spawn_subagent('task')
    except RuntimeError as e:
        if 'depth limit' in str(e):
            # Handle limit

  Retry with backoff:
    async def retry_invoke(agent, name, message, max_retries=3):
        for attempt in range(max_retries):
            result = await agent.invoke_cli(name, message)
            if result.success:
                return result
            await asyncio.sleep(2 ** attempt)
        raise RuntimeError('Max retries exceeded')

  Fallback:
    try:
        result = await agent.invoke_builtin('browser_use', task)
    except Exception:
        result = await agent.invoke_cli('claude', task)
""")


# =============================================================================
# Pattern 8: Configuration Templates
# =============================================================================


async def pattern_config_templates():
    """Recommended configuration patterns."""
    print("\n[P8] Configuration Templates")

    print("""
  Production:
    NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        builtin=[AgentSubagentConfig(name='browser_use', ...)],
        external=[CliSubagentConfig(name='claude', mode='oneshot', timeout=300)],
        max_iterations=20,
        reflection_interval=5,
    )

  Development:
    NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=3,
        enabled_toolkits=['bash', 'wizsearch'],
        max_iterations=5,
    )

  Ask-mode (read-only):
    NoeConfig(
        mode=NoeMode.ASK,
        enable_subagents=False,
    )
""")


# =============================================================================
# Entry Point
# =============================================================================


PATTERNS = [
    pattern_research_delegation,
    pattern_browser_automation,
    pattern_cli_code_assistant,
    pattern_parallel_execution,
    pattern_hierarchical_delegation,
    pattern_progress_tracking,
    pattern_error_handling,
    pattern_config_templates,
]


async def main():
    print("\nNoeAgent Subagent Usage Guide")
    print("=" * 40)

    for pattern in PATTERNS:
        await pattern()

    print("\n" + "=" * 40)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
