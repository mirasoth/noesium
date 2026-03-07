#!/usr/bin/env python3
"""
Claude CLI Subagent Example for NoeAgent.

Requirements:
    - Claude CLI installed: npm install -g @anthropic-claude/claude-code
    - ANTHROPIC_API_KEY environment variable

Usage:
    uv run python examples/noeagent/subagent_claude.py [direct|stream|basic|refactor]
"""

import asyncio
import sys

from noeagent import (
    CliSubagentConfig,
    NoeAgent,
    NoeConfig,
    NoeMode,
    ProgressEvent,
    ProgressEventType,
)

# =============================================================================
# Configuration Factories
# =============================================================================


def basic_config() -> NoeConfig:
    """Basic NoeAgent config with Claude CLI subagent."""
    return NoeConfig(
        mode=NoeMode.AGENT,
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                mode="oneshot",
                output_format="stream-json",
                timeout=300,
                task_types=["code_edit", "code_review", "refactoring"],
                allowed_tools=["Bash", "Edit", "Read", "Write"],
                skip_permissions=True,
            ),
        ],
    )


def advanced_config() -> NoeConfig:
    """Advanced config with multiple CLI subagents."""
    return NoeConfig(
        mode=NoeMode.AGENT,
        max_iterations=20,
        cli_subagents=[
            CliSubagentConfig(
                name="claude",
                command="claude",
                mode="oneshot",
                output_format="stream-json",
                timeout=600,
                task_types=["code_edit", "code_review", "refactoring"],
                allowed_tools=["Bash", "Edit", "Read", "Write", "Grep"],
            ),
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
        enable_subagents=True,
        subagent_max_depth=2,
    )


# =============================================================================
# Progress Handler
# =============================================================================


async def progress_handler(event: ProgressEvent) -> None:
    """Minimal progress event handler."""
    handlers = {
        ProgressEventType.SESSION_START: lambda e: print(f"Session: {e.session_id}"),
        ProgressEventType.PLAN_CREATED: lambda e: print(f"Plan: {e.summary}"),
        ProgressEventType.TOOL_START: lambda e: print(f"  Tool: {e.tool_name}"),
        ProgressEventType.SUBAGENT_START: lambda e: print(f"  Subagent: {e.subagent_id}"),
        ProgressEventType.FINAL_ANSWER: lambda e: print(f"\nAnswer: {e.text}"),
        ProgressEventType.SESSION_END: lambda e: print("Done."),
    }
    if handler := handlers.get(event.type):
        handler(event)


# =============================================================================
# Examples
# =============================================================================


async def example_direct_cli() -> None:
    """Directly invoke Claude CLI without NoeAgent orchestration."""
    from noeagent.cli_adapter import ClaudeCliAdapter

    config = CliSubagentConfig(
        name="claude",
        command="claude",
        mode="oneshot",
        output_format="stream-json",
        timeout=60,
        allowed_tools=["Read"],
    )

    adapter = ClaudeCliAdapter(config)
    task = "What is the purpose of this project? Read README if available."

    print(f"Task: {task}")
    result = await adapter.execute(task)

    if result.success:
        print(f"Completed in {result.execution_time:.1f}s\n{result.content}")
    else:
        print(f"Error: {result.error}")


async def example_streaming() -> str:
    """Stream progress events during execution."""
    config = basic_config()
    agent = NoeAgent(config)

    task = "List the main components in the noesium/toolkits directory"
    print(f"Task: {task}")

    final_result = ""
    async for event in agent.astream_progress(task):
        if event.type == ProgressEventType.THINKING:
            print(f"  Thinking: {event.summary[:60]}")
        elif event.type == ProgressEventType.TOOL_START:
            print(f"  Tool: {event.tool_name}")
        elif event.type == ProgressEventType.FINAL_ANSWER:
            final_result = event.text or ""

    return final_result


async def example_basic_task() -> str:
    """Run a basic code review task."""
    config = basic_config()
    config.progress_callbacks = [progress_handler]

    agent = NoeAgent(config)
    task = "Review noesium/noeagent/agent.py for error handling improvements"

    print(f"Task: {task}")
    return await agent.arun(task)


async def example_refactoring() -> str:
    """Use Claude for code refactoring analysis."""
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
                allowed_tools=["Read", "Grep", "Glob"],
            ),
        ],
    )

    agent = NoeAgent(config)
    task = "Analyze cli_adapter.py and suggest refactoring for better error handling"

    print(f"Task: {task}")
    return await agent.arun(task)


# =============================================================================
# Entry Point
# =============================================================================


EXAMPLES = {
    "direct": example_direct_cli,
    "stream": example_streaming,
    "basic": example_basic_task,
    "refactor": example_refactoring,
}


async def main() -> None:
    # Configure logging (default WARNING, use LOG_LEVEL env var to override)
    import os

    from noesium.core.utils.logging import setup_logging

    setup_logging(level=os.getenv("LOG_LEVEL", "WARNING"), third_party_level="WARNING")

    example = sys.argv[1] if len(sys.argv) > 1 else "direct"

    if example not in EXAMPLES:
        print(f"Unknown: {example}")
        print(f"Usage: {sys.argv[0]} [{'|'.join(EXAMPLES.keys())}]")
        return

    await EXAMPLES[example]()


if __name__ == "__main__":
    asyncio.run(main())
