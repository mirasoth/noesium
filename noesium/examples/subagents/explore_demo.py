"""Example usage of ExploreAgent.

This script demonstrates how to use the ExploreAgent to gather
information from codebases and data sources.
"""

import asyncio

from noesium.subagents import ExploreAgent


async def main():
    """Run ExploreAgent example."""
    print("=" * 80)
    print("ExploreAgent Example: Gathering information")
    print("=" * 80)
    print()

    # Initialize ExploreAgent
    agent = ExploreAgent()

    # Example exploration target
    target = "Explore the authentication module and find all password validation functions"

    print(f"Target: {target}")
    print()
    print("Streaming progress events...")
    print("-" * 80)

    # Stream progress events
    total_findings = 0

    async for event in agent.astream_progress(target):
        event_type = event.type.value
        summary = event.summary or ""

        print(f"[{event_type:20s}] {summary}")

        if event.type.name == "PARTIAL_RESULT":
            total_findings += 1

        elif event.type.name == "FINAL_ANSWER":
            print()
            print("=" * 80)
            print("EXPLORATION FINDINGS:")
            print("=" * 80)
            print(event.text)
            print("=" * 80)

    print()
    print(f"Exploration complete! Found {total_findings} findings.")


if __name__ == "__main__":
    asyncio.run(main())
