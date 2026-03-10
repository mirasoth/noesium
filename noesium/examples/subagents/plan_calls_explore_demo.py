"""Example of PlanAgent calling ExploreAgent.

This script demonstrates how PlanAgent can call ExploreAgent
to gather information during planning.

Note: This is a demonstration of how the agents would work together
when integrated with NoeAgent orchestration.
"""

import asyncio

from noeagent.agent import NoeAgent
from noeagent.config import NoeConfig, NoeMode


async def main():
    """Run integrated example with NoeAgent."""
    print("=" * 80)
    print("Integrated Example: PlanAgent + ExploreAgent with NoeAgent")
    print("=" * 80)
    print()

    # Configure NoeAgent
    config = NoeConfig(mode=NoeMode.AGENT)

    # Initialize NoeAgent
    print("Initializing NoeAgent...")
    agent = NoeAgent(config)

    # Example task that requires both exploration and planning
    task = (
        "Plan the implementation of a new user registration system. "
        "First explore the existing auth code, then create a detailed plan."
    )

    print(f"\nTask: {task}")
    print()
    print("Running with NoeAgent orchestration...")
    print("-" * 80)

    try:
        # Run with NoeAgent
        result = await agent.run(task)

        print()
        print("=" * 80)
        print("RESULT:")
        print("=" * 80)
        print(result)
        print("=" * 80)

    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: This example requires NoeAgent to be fully configured")
        print("with LLM provider and necessary dependencies.")

    print()
    print("Example complete!")


if __name__ == "__main__":
    asyncio.run(main())
