#!/usr/bin/env python3
"""
Simplified TacitusAgent Example

This script demonstrates the core functionality of the TacitusAgent agent.
The main logic is: initialize → research → display results → save to file
"""

import asyncio

from noesium.subagents.tacitus.agent import TacitusAgent


async def main():
    """Simple example of TacitusAgent core functionality with file output."""

    researcher = TacitusAgent(max_research_loops=2, number_of_initial_queries=1)

    topic = "a leisure trip from Seattle to San Francisco via Yellowstone in late September"
    print(f"🔍 Researching: {topic}")

    print("🔄 Starting research...")
    result = await researcher.research(user_message=topic)

    print("\n✅ Research completed!")
    print(f"📄 Summary: {result.summary}")
    print(f"📊 Sources found: {len(result.sources)}")
    print(f"📖 Content: {result.content}")

    # Add source information if available
    source_section = f"\n\n## Sources ({len(result.sources)} found)\n"
    for i, source in enumerate(result.sources, 1):
        if i > 15:
            break
        if isinstance(source, dict):
            url = source.get("value", source.get("url", f"Source {i}"))
            title = source.get("label", source.get("title", f"Source {i}"))
            source_section += f"{i}. [{title}]({url})\n"
        else:
            source_section += f"{i}. {source}\n"
    print(source_section)

    print("\n🎉 Research complete!")


if __name__ == "__main__":
    asyncio.run(main())
