#!/usr/bin/env python3
"""
NoeAgent Demo - Autonomous research assistant with planning capabilities.

This script demonstrates the core functionality of the NoeAgent.
"""

import asyncio

from noesium.noe import NoeAgent


async def main():
    """Simple example of NoeAgent core functionality."""

    # Initialize the agent
    agent = NoeAgent()

    # Run a research task
    topic = "What are the latest developments in quantum computing?"
    print(f"🔍 Researching: {topic}")

    print("🔄 Starting research...")
    result = await agent.arun(topic)

    print(f"\n✅ Research completed!")
    print(f"📖 Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
