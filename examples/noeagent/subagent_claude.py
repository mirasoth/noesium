#!/usr/bin/env python3
"""
Claude CLI Subagent Example for NoeAgent.

This example demonstrates how to integrate Claude Code CLI as a subagent
within NoeAgent, enabling delegation of code-centric tasks like:
- Code review and refactoring
- Multi-file editing
- Complex code analysis

Requirements:
    - Claude CLI installed: npm install -g @anthropic-claude/claude-code
    - Anthropic API key set in environment

Usage:
    uv run python examples/noeagent/subagent_claude.py
"""

import asyncio

from noesium.noeagent import (
    CliSubagentConfig,
    NoeAgent,
    NoeConfig,
    NoeMode,
    ProgressEvent,
    ProgressEventType,
)

# ---------------------------------------------------------------------------
# Example 1: Basic Claude CLI Subagent Configuration
# ---------------------------------------------------------------------------


def create_basic_config() -> NoeConfig:
    """Create a basic NoeAgent config with Claude CLI subagent."""
    return NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                mode="oneshot",  # Recommended: each task spawns fresh process
                output_format="stream-json",
                timeout=300,
                task_types=["code_edit", "code_review", "refactoring"],
                allowed_tools=["Bash", "Edit", "Read", "Write"],
                skip_permissions=True,  # For automation workflows
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Example 2: Advanced Configuration with Multiple CLI Agents
# ---------------------------------------------------------------------------


def create_advanced_config() -> NoeConfig:
    """Create an advanced config with multiple CLI subagents."""
    return NoeConfig(
        mode=NoeMode.AGENT,
        max_iterations=20,
        cli_subagents=[
            # Claude for code tasks
            CliSubagentConfig(
                name="claude",
                command="claude",
                mode="oneshot",
                output_format="stream-json",
                timeout=600,
                task_types=["code_edit", "code_review", "refactoring"],
                allowed_tools=["Bash", "Edit", "Read", "Write", "Grep"],
            ),
            # Claude with restricted tools for safer operations
            CliSubagentConfig(
                name="claude-safe",
                command="claude",
                mode="oneshot",
                output_format="stream-json",
                timeout=300,
                task_types=["code_review", "analysis"],
                allowed_tools=["Read", "Grep"],  # Read-only
            ),
        ],
        # Also enable built-in agents for comparison
        agent_subagents=[],  # Use defaults (browser_use, tacitus)
        enable_subagents=True,
        subagent_max_depth=2,
    )


# ---------------------------------------------------------------------------
# Example 3: Progress Event Handler
# ---------------------------------------------------------------------------


async def progress_handler(event: ProgressEvent) -> None:
    """Handle progress events from NoeAgent execution."""
    if event.type == ProgressEventType.SESSION_START:
        print(f"\n🚀 Session started: {event.session_id}")
    elif event.type == ProgressEventType.PLAN_CREATED:
        print(f"\n📋 Plan created: {event.summary}")
        if event.detail:
            print(f"   {event.detail[:200]}...")
    elif event.type == ProgressEventType.TOOL_START:
        print(f"   🔧 Using tool: {event.tool_name}")
    elif event.type == ProgressEventType.TOOL_END:
        print(f"   ✅ Tool result: {event.tool_result[:100] if event.tool_result else 'done'}...")
    elif event.type == ProgressEventType.SUBAGENT_START:
        print(f"   🤖 Subagent started: {event.subagent_id}")
    elif event.type == ProgressEventType.SUBAGENT_PROGRESS:
        print(f"   🔄 Subagent progress: {event.summary[:80]}...")
    elif event.type == ProgressEventType.SUBAGENT_END:
        print(f"   ✅ Subagent completed: {event.subagent_id}")
    elif event.type == ProgressEventType.FINAL_ANSWER:
        print(f"\n📖 Final Answer:")
        print(f"   {event.text[:500]}..." if len(event.text or "") > 500 else f"   {event.text}")
    elif event.type == ProgressEventType.SESSION_END:
        print(f"\n🏁 Session ended\n")


# ---------------------------------------------------------------------------
# Main Examples
# ---------------------------------------------------------------------------


async def example_basic_task() -> str:
    """Run a basic task using Claude CLI subagent."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Code Review Task")
    print("=" * 60)

    config = create_basic_config()
    config.progress_callbacks = [progress_handler]

    agent = NoeAgent(config)

    task = "Review the noesium/noeagent/agent.py file and suggest improvements for error handling"
    print(f"\nTask: {task}\n")

    result = await agent.arun(task)
    return result


async def example_with_streaming() -> str:
    """Stream progress events during execution."""
    print("\n" + "=" * 60)
    print("Example 2: Streaming Progress Events")
    print("=" * 60)

    config = create_basic_config()

    agent = NoeAgent(config)

    task = "List the main components in the noesium/toolkits directory"
    print(f"\nTask: {task}\n")

    final_result = ""
    async for event in agent.astream_progress(task):
        if event.type == ProgressEventType.THINKING:
            print(f"💭 {event.summary}")
        elif event.type == ProgressEventType.TOOL_START:
            print(f"🔧 Using: {event.tool_name}")
        elif event.type == ProgressEventType.SUBAGENT_START:
            print(f"🤖 Starting subagent: {event.subagent_id}")
        elif event.type == ProgressEventType.SUBAGENT_PROGRESS:
            print(f"   → {event.summary[:80]}")
        elif event.type == ProgressEventType.FINAL_ANSWER:
            final_result = event.text or ""

    return final_result


async def example_direct_cli_invocation() -> None:
    """Directly invoke Claude CLI without NoeAgent orchestration."""
    print("\n" + "=" * 60)
    print("Example 3: Direct Claude CLI Invocation")
    print("=" * 60)

    from noesium.noeagent.cli_adapter import ClaudeCliAdapter

    config = CliSubagentConfig(
        name="claude",
        command="claude",
        mode="oneshot",
        output_format="stream-json",
        timeout=60,
        allowed_tools=["Read"],
    )

    adapter = ClaudeCliAdapter(config)

    task = "What is the purpose of this project? Read the README if available."
    print(f"\nTask: {task}\n")
    print("Executing Claude CLI directly...\n")

    result = await adapter.execute(task)

    if result.success:
        print(f"✅ Success! ({result.execution_time:.2f}s)")
        print(f"\nResponse:\n{result.content}")
    else:
        print(f"❌ Error: {result.error}")


async def example_code_refactoring() -> str:
    """Use Claude for a code refactoring task."""
    print("\n" + "=" * 60)
    print("Example 4: Code Refactoring with Restricted Tools")
    print("=" * 60)

    config = NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="claude-safe",
                command="claude",
                mode="oneshot",
                output_format="stream-json",
                timeout=300,
                task_types=["code_review"],
                allowed_tools=["Read", "Grep", "Glob"],  # Read-only analysis
            ),
        ],
    )

    agent = NoeAgent(config)

    task = "Analyze the cli_adapter.py and suggest refactoring opportunities for better error handling"
    print(f"\nTask: {task}\n")

    result = await agent.arun(task)
    return result


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run examples."""
    import sys

    print("\n" + "=" * 60)
    print("🤖 Claude CLI Subagent Examples for NoeAgent")
    print("=" * 60)
    print("\nThese examples demonstrate Claude Code CLI integration as a subagent.")
    print("Make sure Claude CLI is installed and ANTHROPIC_API_KEY is set.\n")

    # Check for command line args to select example
    example = sys.argv[1] if len(sys.argv) > 1 else "direct"

    if example == "direct":
        # Fastest example - direct CLI invocation
        print("Running: Direct Claude CLI invocation\n")
        await example_direct_cli_invocation()

    elif example == "stream":
        # Streaming progress example
        print("Running: Streaming progress events\n")
        await example_with_streaming()

    elif example == "basic":
        # Basic NoeAgent task
        print("Running: Basic code review task\n")
        await example_basic_task()

    elif example == "refactor":
        # Refactoring example
        print("Running: Code refactoring analysis\n")
        await example_code_refactoring()

    else:
        print(f"Unknown example: {example}")
        print("Usage: uv run python examples/noeagent/subagent_claude.py [direct|stream|basic|refactor]")
        return

    print("\n" + "=" * 60)
    print("✅ Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
