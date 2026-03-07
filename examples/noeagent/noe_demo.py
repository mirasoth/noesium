#!/usr/bin/env python3
"""
NoeAgent Demo - Autonomous research assistant with planning capabilities.

Usage: uv run python examples/noeagent/noe_demo.py
"""

import asyncio
import logging

from noeagent import NoeAgent
from noeagent.config import NoeConfig, NoeMode
from noeagent.progress import ProgressEvent, ProgressEventType

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    """Simple example of NoeAgent core functionality."""
    # Create config with reasonable defaults
    config = NoeConfig(
        mode=NoeMode.AGENT,
        max_iterations=5,
        enabled_toolkits=[],  # No external tools for this simple demo
        enable_session_logging=False,
    )

    agent = NoeAgent(config)

    topic = "What are the latest developments in quantum computing?"
    print(f"Researching: {topic}")
    print("=" * 60)

    # Stream progress events to see what's happening
    event_count = 0
    try:
        async for event in agent.astream_progress(topic):
            event_count += 1
            _print_event(event, event_count)
            if event.type == ProgressEventType.FINAL_ANSWER:
                print("\n" + "=" * 60)
                print("RESULT:")
                print(event.text or "(no answer)")
                break
    except asyncio.TimeoutError:
        print("\nERROR: Operation timed out")
    except Exception as e:
        print(f"\nERROR: {e}")
        raise


def _print_event(event: ProgressEvent, count: int) -> None:
    """Print a progress event in a user-friendly format."""
    event_type = event.type.value

    if event_type == "session.start":
        print("\n[1/3] Starting session...")
    elif event_type == "plan.created":
        print("[2/3] Plan created")
        if event.plan_snapshot:
            steps = event.plan_snapshot.get("steps", [])
            for i, step in enumerate(steps[:5]):  # Show first 5 steps
                desc = step.get("description", "?")[:60]
                print(f"       {i+1}. {desc}")
            if len(steps) > 5:
                print(f"       ... and {len(steps) - 5} more steps")
    elif event_type == "step.start":
        step_desc = (event.step_desc or "Working...")[:50]
        print(f"[3/3] Step {event.step_index}: {step_desc}...")
    elif event_type == "tool.call":
        tool = event.tool_name or "unknown"
        print(f"       → Calling tool: {tool}")
    elif event_type == "subagent.start":
        print(f"       → Subagent: {event.subagent_id}")
    elif event_type == "final.answer":
        pass  # Handled in main
    elif event_type == "session.end":
        print("\nSession completed.")


if __name__ == "__main__":
    asyncio.run(main())
