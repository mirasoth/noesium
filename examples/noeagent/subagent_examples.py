#!/usr/bin/env python3
"""
NoeAgent Subagent Examples - Comprehensive demonstrations of subagent capabilities.

This module demonstrates three types of subagents:
1. In-process child NoeAgent spawning (spawn/interact)
2. Built-in specialized agents (browser_use, tacitus)
3. External CLI subagents (oneshot and daemon modes)

Run with: uv run python examples/noeagent/subagent_examples.py
"""

import asyncio
import logging
import os

from noesium.noeagent import NoeAgent
from noesium.noeagent.config import (
    AgentSubagentConfig,
    CliSubagentConfig,
    NoeConfig,
    NoeMode,
)
from noesium.noeagent.progress import ProgressEvent

# Demo mode - set to False to run actual LLM calls (requires API key)
DEMO_MODE = os.environ.get("NOE_DEMO_MODE", "true").lower() == "true"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Example 1: In-process Child Subagent Spawning
# ---------------------------------------------------------------------------


async def example_child_subagent_spawn():
    """
    Example: Spawning in-process child NoeAgent subagents.

    Child subagents are useful when you need to:
    - Delegate a multi-step task to a specialized worker
    - Maintain isolated execution context
    - Enable parallel task execution

    The parent agent can spawn multiple children and interact with them
    independently. Children inherit the parent's toolkit infrastructure
    but have their own execution state.
    """
    print("\n" + "=" * 70)
    print("Example 1: In-process Child Subagent Spawning")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE - Showing structure without LLM calls]")
        print("\n1. Spawning 'researcher' subagent...")
        print("   subagent_id = await agent.spawn_subagent('researcher', mode=NoeMode.AGENT)")
        print("   -> researcher-1")
        print("   -> Depth: 1")

        print("\n2. Sending task to subagent...")
        print("   result = await agent.interact_with_subagent('researcher-1', 'List files')")
        print("   -> Result: [Subagent would execute the task]")

        print("\n3. Active subagents tracked in agent._subagents dict")
        print("\n4. Cleanup: await agent._cleanup_subagents()")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,  # Allow 2 levels of nesting
        max_iterations=5,
        enabled_toolkits=["bash"],  # Minimal tool set for child
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    # Spawn a child subagent for research tasks
    print("\n1. Spawning 'researcher' subagent...")
    subagent_id = await agent.spawn_subagent(
        "researcher",
        mode=NoeMode.AGENT,
    )
    print(f"   Spawned subagent: {subagent_id}")
    print(f"   Subagent depth: {agent._subagents[subagent_id]._depth}")

    # Interact with the spawned subagent
    print("\n2. Sending task to subagent...")
    task = "List the current directory and tell me what files are present"
    result = await agent.interact_with_subagent(subagent_id, task)
    print(f"   Result: {result[:200]}...")

    # Spawn another child for a different task
    print("\n3. Spawning another subagent 'analyst'...")
    analyst_id = await agent.spawn_subagent("analyst", mode=NoeMode.ASK)
    print(f"   Spawned subagent: {analyst_id}")

    # List all active subagents
    print("\n4. Active subagents:")
    for sid, child in agent._subagents.items():
        print(f"   - {sid} (depth={child._depth})")

    # Cleanup
    await agent._cleanup_subagents()
    print("\n5. Cleaned up all subagents")


async def example_nested_subagents():
    """
    Example: Nested subagent spawning (multi-level delegation).

    Demonstrates depth limits and parent-child relationships.
    """
    print("\n" + "=" * 70)
    print("Example 1b: Nested Subagent Spawning (Depth Limits)")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\nWith subagent_max_depth=3:")
        print("   Parent (depth=0)")
        print("     └── level1 (depth=1)")
        print("           └── level2 (depth=2)")
        print("                 └── level3 (depth=3)")
        print("                       └── level4 -> RuntimeError('depth limit reached')")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=3,
        enabled_toolkits=[],
        enable_session_logging=False,
    )

    parent = NoeAgent(config)
    await parent.initialize()

    print("\n1. Parent agent depth: 0")

    # Level 1
    child1_id = await parent.spawn_subagent("level1")
    child1 = parent._subagents[child1_id]
    print(f"   Level 1: {child1_id} (depth={child1._depth})")

    # Level 2
    child2_id = await child1.spawn_subagent("level2")
    child2 = child1._subagents[child2_id]
    print(f"   Level 2: {child2_id} (depth={child2._depth})")

    # Level 3
    child3_id = await child2.spawn_subagent("level3")
    child3 = child2._subagents[child3_id]
    print(f"   Level 3: {child3_id} (depth={child3._depth})")

    # Level 4 should fail (exceeds max_depth=3)
    print("\n2. Attempting to spawn level 4 (should fail)...")
    try:
        await child3.spawn_subagent("level4")
        print("   ERROR: Should have raised exception!")
    except RuntimeError as e:
        print(f"   Correctly blocked: {e}")

    await parent._cleanup_subagents()


# ---------------------------------------------------------------------------
# Example 2: Built-in Specialized Agents (browser_use, tacitus)
# ---------------------------------------------------------------------------


async def example_builtin_subagent_browser():
    """
    Example: Using the built-in browser_use subagent.

    BrowserUseAgent is ideal for:
    - Web automation and navigation
    - Form filling and submission
    - Data scraping and extraction
    - Screenshot capture

    The browser runs in headless mode by default.
    """
    print("\n" + "=" * 70)
    print("Example 2a: Built-in Browser Use Subagent")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\n1. Configuration:")
        print("   agent_subagents=[")
        print("       AgentSubagentConfig(")
        print("           name='browser_use',")
        print("           agent_type='browser_use',")
        print("           task_types=['web_browsing', 'form_filling', 'scraping'],")
        print("       ),")
        print("   ]")

        print("\n2. Invocation:")
        print("   SubagentAction(action='invoke_builtin', name='browser_use', message='...')")

        print("\n3. Browser runs in headless=True by default")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation for web tasks",
                enabled=True,
                task_types=["web_browsing", "form_filling", "scraping"],
                use_cases=[
                    "Navigate to websites",
                    "Fill out forms",
                    "Extract data from pages",
                ],
                keywords=["browser", "click", "navigate", "web", "page"],
            ),
        ],
        max_iterations=3,
        enabled_toolkits=[],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\n1. Browser use subagent configured:")
    print(f"   - Name: browser_use")
    print(f"   - Headless mode: True (default)")
    print(f"   - Task types: {config.agent_subagents[0].task_types}")

    # Note: Actual browser execution requires LLM API key
    print("\n2. To invoke the browser subagent, NoeAgent's planner would route:")
    print("   SubagentAction(action='invoke_builtin', name='browser_use', message='...')")
    print("   This invokes the BuiltInAgentCapabilityProvider")

    await agent._cleanup_subagents()


async def example_builtin_subagent_tacitus():
    """
    Example: Using the built-in tacitus research subagent.

    TacitusAgent is designed for:
    - Multi-loop web research
    - Iterative query refinement
    - Answer synthesis with citations
    """
    print("\n" + "=" * 70)
    print("Example 2b: Built-in Tacitus Research Subagent")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\n1. Configuration:")
        print("   AgentSubagentConfig(")
        print("       name='tacitus',")
        print("       agent_type='tacitus',")
        print("       task_types=['research', 'web_search', 'citation'],")
        print("   )")

        print("\n2. Tacitus workflow:")
        print("   a. Generate focused search queries")
        print("   b. Execute parallel searches")
        print("   c. Reflect on results for gaps")
        print("   d. Iterate until sufficient")
        print("   e. Synthesize final answer with citations")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        agent_subagents=[
            AgentSubagentConfig(
                name="tacitus",
                agent_type="tacitus",
                description="Deep research agent with reflection",
                enabled=True,
                task_types=["research", "web_search", "citation"],
                use_cases=[
                    "Research complex topics",
                    "Find and synthesize information",
                ],
                keywords=["research", "search", "find", "investigate"],
            ),
        ],
        max_iterations=3,
        enabled_toolkits=[],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\n1. Tacitus subagent configured:")
    print(f"   - Name: tacitus")
    print(f"   - Task types: {config.agent_subagents[0].task_types}")
    print("\n2. Tacitus workflow:")
    print("   - Generate focused search queries")
    print("   - Execute parallel searches")
    print("   - Reflect on results for gaps")
    print("   - Iterate until sufficient")
    print("   - Synthesize final answer with citations")

    await agent._cleanup_subagents()


# ---------------------------------------------------------------------------
# Example 3: CLI Subagent Integration
# ---------------------------------------------------------------------------


async def example_cli_subagent_oneshot():
    """
    Example: CLI subagent in oneshot mode.

    Oneshot mode:
    - Spawns a new process for each invocation
    - Process exits after completing the task
    - Ideal for stateless operations
    - Recommended for CLI tools like Claude Code CLI
    """
    print("\n" + "=" * 70)
    print("Example 3a: CLI Subagent - Oneshot Mode")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\n1. Configuration:")
        print("   cli_subagents=[")
        print("       CliSubagentConfig(")
        print("           name='claude',")
        print("           command='claude',")
        print("           args=['--output-format', 'stream-json'],")
        print("           mode='oneshot',")
        print("           timeout=300,")
        print("           skip_permissions=True,")
        print("           task_types=['code_edit', 'refactor'],")
        print("           allowed_tools=['Bash', 'Edit', 'Read'],")
        print("       ),")
        print("   ]")

        print("\n2. Oneshot execution flow:")
        print("   a. SubagentAction(action='invoke_cli', name='claude', message='...')")
        print("   b. Spawn new process: claude -p --output-format stream-json")
        print("   c. Send message via stdin")
        print("   d. Capture and parse NDJSON output")
        print("   e. Return result (process exits)")

        print("\n3. Options:")
        print("   - allowed_tools: Restrict available tools")
        print("   - skip_permissions: Auto-approve operations")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                args=["--output-format", "stream-json"],
                mode="oneshot",  # Each invocation spawns new process
                timeout=300,
                skip_permissions=True,
                task_types=["code_edit", "code_review", "refactor"],
                allowed_tools=["Bash", "Edit", "Read", "Write"],
            ),
        ],
        max_iterations=3,
        enabled_toolkits=[],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\n1. CLI subagent configured:")
    print(f"   - Name: claude")
    print(f"   - Mode: oneshot")
    print(f"   - Command: claude --output-format stream-json")
    print(f"   - Timeout: 300s")
    print(f"   - Allowed tools: {config.cli_subagents[0].allowed_tools}")

    print("\n2. Oneshot execution flow:")
    print("   a. Receive SubagentAction(action='invoke_cli', name='claude', message='...')")
    print("   b. Spawn new process: claude -p --output-format stream-json")
    print("   c. Send message via stdin")
    print("   d. Capture and parse NDJSON output")
    print("   e. Return result (process exits)")

    print("\n3. Options for invoke_cli:")
    print("   - allowed_tools: Restrict tools available to CLI agent")
    print("   - skip_permissions: Auto-approve dangerous operations")

    await agent._cleanup_subagents()


async def example_cli_subagent_daemon():
    """
    Example: CLI subagent in daemon mode.

    Daemon mode:
    - Spawns a persistent long-lived process
    - Maintains state across multiple interactions
    - Bidirectional JSON streaming via stdin/stdout
    - Useful for stateful sessions
    """
    print("\n" + "=" * 70)
    print("Example 3b: CLI Subagent - Daemon Mode")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\n1. Configuration:")
        print("   CliSubagentConfig(")
        print("       name='persistent-agent',")
        print("       mode='daemon',")
        print("       restart_policy='on-failure',")
        print("   )")

        print("\n2. Daemon lifecycle:")
        print("   a. spawn_cli: Start persistent process")
        print("   b. interact_cli: Send messages to running daemon")
        print("   c. interact_cli: Continue conversation...")
        print("   d. terminate_cli: Shut down daemon")

        print("\n3. SubagentActions:")
        print("   - action='spawn_cli': Start the daemon")
        print("   - action='interact_cli': Send message to running daemon")
        print("   - action='terminate_cli': Stop the daemon")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="persistent-agent",
                command="custom-agent-cli",
                args=["--daemon-mode"],
                mode="daemon",  # Persistent process
                output_format="stream-json",
                timeout=600,
                restart_policy="on-failure",  # Auto-restart on crash
                task_types=["long_running", "stateful"],
            ),
        ],
        max_iterations=3,
        enabled_toolkits=[],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\n1. Daemon mode configuration:")
    print(f"   - Name: persistent-agent")
    print(f"   - Mode: daemon")
    print(f"   - Restart policy: on-failure")

    print("\n2. Daemon lifecycle:")
    print("   a. spawn_cli: Start persistent process")
    print("   b. interact_cli: Send messages to running daemon")
    print("   c. interact_cli: Continue conversation...")
    print("   d. terminate_cli: Shut down daemon")

    print("\n3. SubagentActions for daemon:")
    print("   - action='spawn_cli': Start the daemon")
    print("   - action='interact_cli': Send message to running daemon")
    print("   - action='terminate_cli': Stop the daemon")


# ---------------------------------------------------------------------------
# Example 4: Progress Event Streaming
# ---------------------------------------------------------------------------


async def example_progress_streaming():
    """
    Example: Streaming progress events from subagent execution.

    Progress events provide real-time visibility into:
    - Task planning and execution
    - Tool invocations and results
    - Subagent lifecycle (start, progress, end)
    - Final answer synthesis
    """
    print("\n" + "=" * 70)
    print("Example 4: Progress Event Streaming")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\n1. Configure progress callback:")
        print("   config = NoeConfig(")
        print("       progress_callbacks=[my_callback],")
        print("   )")

        print("\n2. Progress event types:")
        print("   - SESSION_START: Agent session begins")
        print("   - PLAN_CREATED: Task plan generated")
        print("   - STEP_START/END: Plan step execution")
        print("   - TOOL_CALL: Tool invocation")
        print("   - SUBAGENT_START/PROGRESS/END: Subagent activity")
        print("   - FINAL_ANSWER: Task completed")
        print("   - SESSION_END: Session finished")

        print("\n3. Subagent events include:")
        print("   - subagent_id: Identifier for the subagent")
        print("   - step_index/step_desc: Current plan step")
        print("   - plan_snapshot: Current plan state")
        return

    # Custom callback to collect events
    events: list[ProgressEvent] = []

    async def event_callback(event: ProgressEvent):
        events.append(event)
        event_type = event.type.value
        summary = event.summary or ""
        print(f"   [{event_type}] {summary[:60]}...")

    config = NoeConfig(
        mode=NoeMode.AGENT,
        enable_subagents=True,
        subagent_max_depth=2,
        max_iterations=3,
        progress_callbacks=[event_callback],
        enabled_toolkits=[],
        enable_session_logging=False,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\n1. Progress event types:")
    print("   - SESSION_START: Agent session begins")
    print("   - PLAN_CREATED: Task plan generated")
    print("   - STEP_START/STEP_END: Plan step execution")
    print("   - TOOL_CALL: Tool invocation")
    print("   - SUBAGENT_START/PROGRESS/END: Subagent activity")
    print("   - FINAL_ANSWER: Task completed")
    print("   - SESSION_END: Session finished")

    print("\n2. Subagent events include:")
    print("   - subagent_id: Identifier for the subagent")
    print("   - step_index/step_desc: Current plan step")
    print("   - plan_snapshot: Current plan state")

    await agent._cleanup_subagents()


# ---------------------------------------------------------------------------
# Example 5: Complete Integration Example
# ---------------------------------------------------------------------------


async def example_complete_integration():
    """
    Example: Complete integration with all subagent types.

    Demonstrates a realistic NoeAgent setup with:
    - Child subagent spawning
    - Browser automation subagent
    - Research subagent
    - CLI subagent integration
    """
    print("\n" + "=" * 70)
    print("Example 5: Complete Integration (All Subagent Types)")
    print("=" * 70)

    if DEMO_MODE:
        print("\n[DEMO MODE]")
        print("\nComplete NoeConfig with all subagent types:")
        print("""
config = NoeConfig(
    mode=NoeMode.AGENT,
    # Child subagent spawning
    enable_subagents=True,
    subagent_max_depth=2,
    
    # Built-in agent subagents
    agent_subagents=[
        AgentSubagentConfig(
            name='browser_use',
            agent_type='browser_use',
            task_types=['web_browsing', 'form_filling'],
        ),
        AgentSubagentConfig(
            name='tacitus',
            agent_type='tacitus',
            task_types=['research', 'search'],
        ),
    ],
    
    # CLI subagents
    cli_subagents=[
        CliSubagentConfig(
            name='claude',
            command='claude',
            mode='oneshot',
            task_types=['code_edit', 'refactor'],
        ),
    ],
    
    # Tools
    enabled_toolkits=['bash', 'wizsearch'],
    max_iterations=10,
)
""")

        print("\nSubagent routing logic:")
        print("   1. TaskPlanner analyzes task requirements")
        print("   2. Matches task to subagent capabilities")
        print("   3. Generates appropriate SubagentAction:")
        print("      - 'spawn': Create in-process child")
        print("      - 'invoke_builtin': Use browser_use or tacitus")
        print("      - 'invoke_cli': Execute external CLI agent")
        return

    config = NoeConfig(
        mode=NoeMode.AGENT,
        # Enable child subagent spawning
        enable_subagents=True,
        subagent_max_depth=2,
        # Built-in agent subagents
        agent_subagents=[
            AgentSubagentConfig(
                name="browser_use",
                agent_type="browser_use",
                description="Browser automation agent",
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
        # CLI subagents
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
        # Tool configuration
        enabled_toolkits=["bash", "wizsearch"],
        max_iterations=10,
        reflection_interval=3,
        enable_session_logging=True,
    )

    agent = NoeAgent(config)
    await agent.initialize()

    print("\n1. Configuration summary:")
    print(f"   - Mode: {config.mode.value}")
    print(f"   - Subagents enabled: {config.enable_subagents}")
    print(f"   - Max depth: {config.subagent_max_depth}")
    print(f"   - Built-in agents: {[s.name for s in config.agent_subagents]}")
    print(f"   - CLI agents: {[s.name for s in config.cli_subagents]}")
    print(f"   - Toolkits: {config.enabled_toolkits}")

    print("\n2. Capability registry contents:")
    if agent._registry:
        for provider in agent._registry.list_providers():
            desc = provider.descriptor
            print(f"   - {desc.capability_id}: {desc.description[:50]}...")

    print("\n3. Subagent routing logic (in TaskPlanner):")
    print("   a. Analyze task complexity and requirements")
    print("   b. Match task types to subagent capabilities")
    print("   c. Generate SubagentAction with appropriate action type:")
    print("      - 'spawn': Create in-process child NoeAgent")
    print("      - 'invoke_builtin': Use browser_use or tacitus")
    print("      - 'invoke_cli': Execute external CLI agent")

    await agent._cleanup_subagents()
    print("\n4. Session complete, all subagents cleaned up")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


async def main():
    """Run all subagent examples."""
    print("\n" + "=" * 70)
    print("NoeAgent Subagent Examples")
    print("=" * 70)

    # Example 1: In-process child subagents
    await example_child_subagent_spawn()
    await example_nested_subagents()

    # Example 2: Built-in specialized agents
    await example_builtin_subagent_browser()
    await example_builtin_subagent_tacitus()

    # Example 3: CLI subagent integration
    await example_cli_subagent_oneshot()
    await example_cli_subagent_daemon()

    # Example 4: Progress streaming
    await example_progress_streaming()

    # Example 5: Complete integration
    await example_complete_integration()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
