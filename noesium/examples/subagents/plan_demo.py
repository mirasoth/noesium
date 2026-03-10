"""Example usage of PlanAgent.

This script demonstrates how to use the PlanAgent to create
implementation plans for complex tasks.
"""

import asyncio

from noesium.subagents import PlanAgent


async def main():
    """Run PlanAgent example."""
    print("=" * 80)
    print("PlanAgent Example: Creating an implementation plan")
    print("=" * 80)
    print()

    # Initialize PlanAgent
    agent = PlanAgent()

    # Example task
    task = "Create a plan to implement a REST API with authentication"

    print(f"Task: {task}")
    print()
    print("Streaming progress events...")
    print("-" * 80)

    # Stream progress events
    async for event in agent.astream_progress(task):
        event_type = event.type.value
        summary = event.summary or ""

        print(f"[{event_type:20s}] {summary}")

        if event.type.name == "PLAN_CREATED":
            steps = event.plan_snapshot.get("steps", [])
            print(f"\n  Plan has {len(steps)} steps:")
            for _, step in enumerate(steps, 1):
                print(f"    {step.get('description', 'Unknown')}")
            print()

        elif event.type.name == "FINAL_ANSWER":
            print()
            print("=" * 80)
            print("FINAL PLAN:")
            print("=" * 80)
            print(event.text)
            print("=" * 80)

    print()
    print("Planning complete!")


if __name__ == "__main__":
    asyncio.run(main())
