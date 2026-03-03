#!/usr/bin/env python3
"""
NoeAgent Subagent Usage Guide - Practical patterns and best practices.

This guide demonstrates real-world usage patterns for NoeAgent subagents.

Run with: uv run python examples/noeagent/subagent_usage_guide.py
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

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise for examples
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# =============================================================================
# PATTERN 1: Simple Research Task with Child Subagent
# =============================================================================


async def pattern_simple_research():
    """
    Pattern: Delegate a focused research task to a child subagent.

    Use case: You have a complex research task that benefits from
    isolated execution and dedicated planning.
    """
    print("\n" + "=" * 60)
    print("Pattern 1: Simple Research Task Delegation")
    print("=" * 60)

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

    # Spawn a research subagent
    subagent_id = await agent.spawn_subagent(
        "web-researcher",
        mode=NoeMode.AGENT,
    )

    # Delegate a focused task
    task = """
    Research the latest Python 3.12 features and provide a summary of:
    1. Performance improvements
    2. New syntax features
    3. Breaking changes from Python 3.11
    """

    print(f"\nDelegating task to '{subagent_id}'...")
    print(f"Task: {task.strip()[:100]}...")

    # In production, this would execute the full research
    # result = await agent.interact_with_subagent(subagent_id, task)
    # print(f"\nResult: {result}")

    print("\n[Demo mode - skipping actual execution]")

    await agent._cleanup_subagents()


# =============================================================================
# PATTERN 2: Browser Automation with Built-in Subagent
# =============================================================================


async def pattern_browser_automation():
    """
    Pattern: Use browser_use subagent for web automation.

    Use case: Automate web interactions like form filling,
    data extraction, or navigation workflows.
    """
    print("\n" + "=" * 60)
    print("Pattern 2: Browser Automation (Built-in Subagent)")
    print("=" * 60)

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation agent",
                enabled=True,
                task_types=["web_automation", "scraping", "form_filling"],
                # Semantic routing hints
                keywords=["browser", "click", "navigate", "fill", "scrape"],
                preferred_for=["interactive web tasks", "form submission"],
            ),
        ],
        enabled_toolkits=[],
        max_iterations=3,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    # The planner would automatically route browser-related tasks
    # to the browser_use subagent based on task_types and keywords
    print("\nBrowser subagent is registered and ready.")
    print("\nExample tasks that would be routed to browser_use:")
    print("  - 'Navigate to example.com and take a screenshot'")
    print("  - 'Fill out the contact form with test data'")
    print("  - 'Scrape product prices from the e-commerce page'")

    print("\nRouting flow:")
    print("  1. User task -> TaskPlanner.create_plan()")
    print("  2. Planner matches task to subagent by task_types/keywords")
    print("  3. Execute step with execution_hint='builtin_agent'")
    print("  4. SubagentAction(action='invoke_builtin', name='browser_use')")

    await agent._cleanup_subagents()


# =============================================================================
# PATTERN 3: CLI Subagent for Code Tasks
# =============================================================================


async def pattern_cli_code_assistant():
    """
    Pattern: Use CLI subagent for code editing tasks.

    Use case: Delegate code modifications to an external CLI agent
    like Claude Code CLI for specialized code operations.
    """
    print("\n" + "=" * 60)
    print("Pattern 3: CLI Subagent for Code Tasks")
    print("=" * 60)

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
                task_types=["code_edit", "code_review", "refactor", "debug"],
                allowed_tools=["Bash", "Edit", "Read", "Write", "Glob", "Grep"],
            ),
        ],
        enabled_toolkits=["bash"],
        max_iterations=5,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\nCLI subagent 'claude' configured:")
    print(f"  Mode: oneshot (new process per invocation)")
    print(f"  Timeout: 300s")
    print(f"  Allowed tools: {config.cli_subagents[0].allowed_tools}")

    print("\nExample usage scenarios:")
    print("\n1. Code refactoring:")
    print("   SubagentAction(")
    print("       action='invoke_cli',")
    print("       name='claude',")
    print("       message='Refactor the authentication module to use async/await',")
    print("       allowed_tools=['Edit', 'Read', 'Bash']")
    print("   )")

    print("\n2. Code review:")
    print("   SubagentAction(")
    print("       action='invoke_cli',")
    print("       name='claude',")
    print("       message='Review src/api.py for security issues',")
    print("       skip_permissions=True")
    print("   )")

    print("\n3. Bug investigation:")
    print("   SubagentAction(")
    print("       action='invoke_cli',")
    print("       name='claude',")
    print("       message='Find and fix the memory leak in the worker process'")
    print("   )")

    await agent._cleanup_subagents()


# =============================================================================
# PATTERN 4: Multi-Agent Parallel Execution
# =============================================================================


async def pattern_parallel_subagents():
    """
    Pattern: Spawn multiple subagents for parallel task execution.

    Use case: When you have independent tasks that can run concurrently.
    """
    print("\n" + "=" * 60)
    print("Pattern 4: Parallel Subagent Execution")
    print("=" * 60)

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        enabled_toolkits=["bash"],
        max_iterations=3,
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    # Spawn multiple subagents
    print("\nSpawning multiple subagents...")

    subagent1_id = await agent.spawn_subagent("task-analyzer", mode=NoeMode.ASK)
    subagent2_id = await agent.spawn_subagent("data-collector", mode=NoeMode.AGENT)
    subagent3_id = await agent.spawn_subagent("report-writer", mode=NoeMode.ASK)

    print(f"  1. {subagent1_id} - for analyzing task requirements")
    print(f"  2. {subagent2_id} - for collecting data")
    print(f"  3. {subagent3_id} - for writing reports")

    # Execute tasks in parallel
    print("\nParallel execution pattern:")

    async def run_parallel():
        # In production, these would run actual tasks
        tasks = [
            agent.interact_with_subagent(subagent1_id, "Analyze the input data format"),
            agent.interact_with_subagent(subagent2_id, "Collect sample data"),
            agent.interact_with_subagent(subagent3_id, "Draft report template"),
        ]
        # results = await asyncio.gather(*tasks)
        # return results
        print("  [Demo mode - would execute asyncio.gather()]")

    await run_parallel()

    print("\nBenefits of parallel execution:")
    print("  - Reduced total execution time")
    print("  - Better resource utilization")
    print("  - Independent error handling per subagent")

    await agent._cleanup_subagents()


# =============================================================================
# PATTERN 5: Hierarchical Task Delegation
# =============================================================================


async def pattern_hierarchical_delegation():
    """
    Pattern: Hierarchical task delegation with nested subagents.

    Use case: Complex tasks requiring multiple levels of delegation.
    """
    print("\n" + "=" * 60)
    print("Pattern 5: Hierarchical Task Delegation")
    print("=" * 60)

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=3,  # Allow 3 levels
        enabled_toolkits=["bash"],
        max_iterations=3,
        enable_session_logging=False,
    )

    parent = NoeAgent(config)
    await parent.initialize()

    print("\nHierarchical structure:")

    # Level 1: Coordinator
    coord_id = await parent.spawn_subagent("coordinator")
    coordinator = parent._subagents[coord_id]
    print(f"  Level 1: {coord_id} (coordinator)")
    print(f"           Depth: {coordinator._depth}")

    # Level 2: Workers
    worker1_id = await coordinator.spawn_subagent("worker-1")
    worker2_id = await coordinator.spawn_subagent("worker-2")
    print(f"  Level 2: {worker1_id}, {worker2_id} (workers)")

    # Level 3: Specialists
    worker1 = coordinator._subagents[worker1_id]
    spec_id = await worker1.spawn_subagent("specialist")
    print(f"  Level 3: {spec_id} (specialist)")

    print("\nTask flow:")
    print("  1. Parent delegates to coordinator")
    print("  2. Coordinator splits work among workers")
    print("  3. Workers may delegate to specialists")
    print("  4. Results bubble up through the hierarchy")

    print("\nDepth protection:")
    print(f"  Max depth: {config.subagent_max_depth}")
    print("  Prevents infinite recursion")

    await parent._cleanup_subagents()


# =============================================================================
# PATTERN 6: Progress Tracking with Callbacks
# =============================================================================


async def pattern_progress_tracking():
    """
    Pattern: Track subagent progress with event callbacks.

    Use case: Real-time monitoring of long-running tasks.
    """
    print("\n" + "=" * 60)
    print("Pattern 6: Progress Tracking with Callbacks")
    print("=" * 60)

    events_log: list[str] = []

    async def progress_callback(event: ProgressEvent):
        """Track and display progress events."""
        event_type = event.type.value
        summary = (event.summary or "")[:50]

        # Build log entry
        entry = f"[{event_type}]"
        if event.subagent_id:
            entry += f" subagent={event.subagent_id}"
        if event.step_index is not None:
            entry += f" step={event.step_index}"
        if event.tool_name:
            entry += f" tool={event.tool_name}"
        if summary:
            entry += f" {summary}"

        events_log.append(entry)
        print(f"  {entry}")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        enabled_toolkits=["bash"],
        max_iterations=3,
        progress_callbacks=[progress_callback],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\nRegistered progress callback.")
    print("\nExample event stream during subagent execution:")

    # Simulate event stream
    print("  [session_start] session=abc123")
    print("  [plan_created] 3 steps")
    print("  [step_start] step=0")
    print("  [tool_call] tool=bash")
    print("  [subagent_start] subagent=worker-1")
    print("  [subagent_progress] subagent=worker-1 Executing task...")
    print("  [subagent_end] subagent=worker-1 Completed")
    print("  [step_end] step=0")
    print("  [final_answer] Task completed successfully")
    print("  [session_end]")

    print("\nKey event types for subagents:")
    print("  - SUBAGENT_START: Subagent spawned")
    print("  - SUBAGENT_PROGRESS: Subagent activity update")
    print("  - SUBAGENT_END: Subagent completed")

    await agent._cleanup_subagents()


# =============================================================================
# PATTERN 7: Error Handling and Recovery
# =============================================================================


async def pattern_error_handling():
    """
    Pattern: Handle subagent errors gracefully.

    Use case: Robust task execution with error recovery.
    """
    print("\n" + "=" * 60)
    print("Pattern 7: Error Handling and Recovery")
    print("=" * 60)

    print("\nCommon error scenarios:")

    print("\n1. Subagent depth limit exceeded:")
    print("   try:")
    print("       await agent.spawn_subagent('task')")
    print("   except RuntimeError as e:")
    print("       if 'depth limit' in str(e):")
    print("           # Handle depth limit")
    print("           pass")

    print("\n2. Unknown subagent:")
    print("   result = await agent.interact_with_subagent('unknown', 'task')")
    print("   # Raises KeyError: Unknown subagent")

    print("\n3. CLI command not found:")
    print("   # CliExecutionResult(success=False, error='Command not found')")

    print("\n4. CLI timeout:")
    print("   # CliExecutionResult(success=False, error='timed out after 300s')")

    print("\n5. Built-in agent invocation failure:")
    print("   # result: 'Failed to invoke built-in agent: ...'")

    print("\nRecovery patterns:")

    print("\n1. Retry with exponential backoff:")
    print("   async def retry_invoke(agent, name, message, max_retries=3):")
    print("       for attempt in range(max_retries):")
    print("           result = await agent.invoke_cli(name, message)")
    print("           if result.success:")
    print("               return result")
    print("           await asyncio.sleep(2 ** attempt)")
    print("       raise RuntimeError('Max retries exceeded')")

    print("\n2. Fallback to alternative subagent:")
    print("   try:")
    print("       result = await agent.invoke_builtin('browser_use', task)")
    print("   except Exception:")
    print("       # Fallback to CLI agent")
    print("       result = await agent.invoke_cli('claude', task)")

    print("\n3. Partial result handling:")
    print("   # Check tool_results for partial successes")
    print("   for result in state['tool_results']:")
    print("       if 'Error:' not in result['result']:")
    print("           # Process successful results")


# =============================================================================
# PATTERN 8: Configuration Best Practices
# =============================================================================


async def pattern_configuration_best_practices():
    """
    Pattern: Recommended configuration patterns.
    """
    print("\n" + "=" * 60)
    print("Pattern 8: Configuration Best Practices")
    print("=" * 60)

    print("\n1. Production configuration:")
    print("""
    config = NoeConfig(
        mode=NoeMode.AGENT,
        # Subagent settings
        enable_subagents=True,
        subagent_max_depth=2,  # Prevent runaway nesting
        # Built-in agents
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                enabled=True,
                task_types=["web_automation"],
            ),
        ],
        # CLI agents
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                mode="oneshot",  # Stateless execution
                timeout=300,
                skip_permissions=True,
            ),
        ],
        # Execution limits
        max_iterations=20,
        reflection_interval=5,
        # Logging
        enable_session_logging=True,
    )
    """)

    print("\n2. Development configuration:")
    print("""
    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=3,  # More flexibility for debugging
        enabled_toolkits=["bash", "wizsearch"],
        max_iterations=5,
        enable_session_logging=False,  # Less noise
    )
    """)

    print("\n3. Ask-mode (read-only) configuration:")
    print("""
    config = NoeConfig(
        mode=NoeMode.ASK,  # Q&A mode, no tool execution
        enable_subagents=False,
        memory_providers=["working", "memu"],
    )
    """)

    print("\n4. CLI subagent mode selection:")
    print("""
    # Oneshot: New process per invocation (recommended)
    CliSubagentConfig(
        name="claude",
        mode="oneshot",
        timeout=300,
    )

    # Daemon: Persistent process (for stateful sessions)
    CliSubagentConfig(
        name="persistent-agent",
        mode="daemon",
        restart_policy="on-failure",
    )
    """)


# =============================================================================
# Main Entry Point
# =============================================================================


async def main():
    """Run all patterns."""
    print("\n" + "=" * 60)
    print("NoeAgent Subagent Usage Guide")
    print("Practical Patterns and Best Practices")
    print("=" * 60)

    await pattern_simple_research()
    await pattern_browser_automation()
    await pattern_cli_code_assistant()
    await pattern_parallel_subagents()
    await pattern_hierarchical_delegation()
    await pattern_progress_tracking()
    await pattern_error_handling()
    await pattern_configuration_best_practices()

    print("\n" + "=" * 60)
    print("All patterns demonstrated!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
