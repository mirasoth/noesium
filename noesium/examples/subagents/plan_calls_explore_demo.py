"""Example of PlanAgent working with ExploreAgent.

This script demonstrates how to use PlanAgent directly with its built-in
exploration capabilities, or manually combine ExploreAgent results with PlanAgent.

PlanAgent has built-in exploration via its _explore_resources_node that uses
file_edit tools to gather context before planning.
"""

import asyncio
from pathlib import Path

from noesium.core.event import ProgressEvent, ProgressEventType
from noesium.subagents.explore import ExploreAgent
from noesium.subagents.plan import PlanAgent


async def main():
    """Run PlanAgent directly with optional ExploreAgent integration."""
    print("=" * 80)
    print("Direct Usage: PlanAgent with Built-in Exploration")
    print("=" * 80)
    print()

    # Get working directory (explore the noesium codebase)
    workspace = Path(__file__).parent.parent.parent  # noesium/
    working_dir = str(workspace)

    # Example task that requires exploration and planning
    task = (
        "Plan the implementation of a new user registration system. "
        "Explore the existing auth code structure and create a detailed plan."
    )

    print(f"Working directory: {working_dir}")
    print(f"\nTask: {task}")
    print("-" * 80)

    # Method 1: PlanAgent with built-in exploration (simpler)
    print("\n[Method 1] PlanAgent with built-in exploration:")
    print("-" * 40)

    plan_agent = PlanAgent(
        llm_provider="openai",
        max_planning_loops=2,
        working_directory=working_dir,
    )

    try:
        # Stream progress events
        async for event in plan_agent.astream_progress(task):
            _print_event(event)

        # Get the final result
        result = await plan_agent.run(task)

        print("\n" + "=" * 80)
        print("PLAN RESULT:")
        print("=" * 80)
        print(result)
        print("=" * 80)

    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: This example requires LLM provider to be configured.")
        print("Set NOESIUM_LLM_PROVIDER and appropriate API keys.")

    # Method 2: Manual ExploreAgent -> PlanAgent pipeline (more control)
    print("\n\n" + "=" * 80)
    print("[Method 2] Manual ExploreAgent -> PlanAgent pipeline:")
    print("-" * 40)

    explore_agent = ExploreAgent(
        llm_provider="openai",
        max_exploration_depth=2,
        working_directory=working_dir,
    )

    plan_agent2 = PlanAgent(
        llm_provider="openai",
        max_planning_loops=2,
        working_directory=working_dir,
    )

    try:
        # Step 1: Explore first
        print("\nStep 1: Exploring codebase...")
        exploration_target = "Find authentication-related code and user models"

        explore_result = await explore_agent.run(exploration_target)

        print(f"\nExploration found {explore_result.finding_count} findings:")
        for i, finding in enumerate(explore_result.findings[:3], 1):
            print(f"  {i}. {finding.title}: {finding.summary[:60]}...")

        # Step 2: Use exploration results as context for planning
        print("\nStep 2: Creating plan with exploration context...")

        # Build context from exploration
        context = {
            "exploration_summary": explore_result.summary,
            "key_findings": [{"title": f.title, "summary": f.summary} for f in explore_result.findings[:5]],
        }

        plan_result = await plan_agent2.run(
            user_message=task,
            context=context,  # Pass exploration results as context
        )

        print("\n" + "=" * 80)
        print("PLAN WITH EXPLORATION CONTEXT:")
        print("=" * 80)
        print(plan_result)
        print("=" * 80)

    except Exception as e:
        print(f"\nError: {e}")

    print("\nExample complete!")


def _print_event(event: ProgressEvent) -> None:
    """Print a progress event."""
    event.type.value if hasattr(event.type, "value") else str(event.type)

    if event.type == ProgressEventType.THINKING:
        print(f"  [thinking] {event.summary}")
    elif event.type == ProgressEventType.TOOL_START:
        print(f"  [tool] Using {event.tool_name}...")
    elif event.type == ProgressEventType.TOOL_END:
        status = "✓" if "success" in (event.tool_result or "").lower() else "→"
        print(f"  [tool] {status} {event.tool_name}: {event.summary[:50]}...")
    elif event.type == ProgressEventType.PLAN_CREATED:
        print(f"  [plan] {event.summary}")
    elif event.type == ProgressEventType.FINAL_ANSWER:
        print(f"  [done] {event.summary}")


if __name__ == "__main__":
    asyncio.run(main())
