#!/usr/bin/env python3
"""
NoeAgent Demo - Autonomous research assistant with planning capabilities.

Usage: uv run python examples/noeagent/noe_demo.py
"""

import asyncio

from noesium.noeagent import NoeAgent


async def main():
    """Simple example of NoeAgent core functionality."""
    agent = NoeAgent()

    topic = "What are the latest developments in quantum computing?"
    print(f"Researching: {topic}")

    result = await agent.arun(topic)
    print(f"\nResult:\n{result}")


if __name__ == "__main__":
    asyncio.run(main())
