#!/usr/bin/env python3
"""
Wikipedia T2Agent Demo

This example demonstrates complex web interactions with Wikipedia using the T2Agent
implementation with browser-use integration.

Features demonstrated:
1. Navigation to Wikipedia
2. Search functionality
3. Article navigation
4. Content extraction from Wikipedia articles
5. Following links and exploring related content

Requirements:
- OpenAI API key (set OPENAI_API_KEY environment variable)
- Browser-use library (included in thirdparty/)
"""

import asyncio
import sys
from typing import List

from pydantic import BaseModel

from noesium.agents.t2 import T2Agent
from noesium.core.llm import get_llm_client
from noesium.core.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)
llm_client = get_llm_client(structured_output=True)


class WikipediaArticle(BaseModel):
    """Schema for extracting Wikipedia article data"""

    title: str
    summary: str
    main_sections: List[str]
    categories: List[str]


async def demo_wikipedia_search():
    """Demonstrate Wikipedia search functionality."""
    logger.info("🔍 Demo: Wikipedia Search")

    t2_agent = T2Agent(llm=llm_client)

    try:
        # Navigate to Wikipedia and search for "Artificial Intelligence"
        result = await t2_agent.navigate_and_act(
            url="https://en.wikipedia.org",
            instruction="Search for 'Artificial Intelligence' using the search box",
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Search completed: {result}")

        # Wait a moment for the page to load
        await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"❌ Search demo failed: {e}")
        raise


async def demo_wikipedia_article_extraction():
    """Demonstrate extracting structured data from Wikipedia articles."""
    logger.info("📊 Demo: Wikipedia Article Extraction")

    t2_agent = T2Agent(llm=llm_client)

    try:
        # Extract structured information from the Machine Learning article
        article_data = await t2_agent.navigate_and_extract(
            url="https://en.wikipedia.org/wiki/Machine_learning",
            instruction="Extract the article title, first paragraph summary, main section headings, and categories",
            schema=WikipediaArticle,
        )

        logger.info("✅ Extracted article data:")
        if isinstance(article_data, WikipediaArticle):
            logger.info(f"  Title: {article_data.title}")
            logger.info(f"  Summary: {article_data.summary[:200]}...")
            logger.info(f"  Main sections: {', '.join(article_data.main_sections[:5])}")
            logger.info(f"  Categories: {', '.join(article_data.categories[:3])}")
        else:
            logger.info(f"  Raw data: {article_data}")

    except Exception as e:
        logger.error(f"❌ Article extraction demo failed: {e}")
        raise


async def demo_wikipedia_navigation():
    """Demonstrate navigating between Wikipedia articles."""
    logger.info("🧭 Demo: Wikipedia Navigation")

    t2_agent = T2Agent(llm=llm_client)

    try:
        # Start at Python programming language article and navigate to related content
        result = await t2_agent.navigate_and_act(
            url="https://en.wikipedia.org/wiki/Python_(programming_language)",
            instruction="Click on the first link in the 'See also' section or find a link related to 'machine learning' or 'data science'",
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Navigation result: {result}")

        # Wait for navigation
        await asyncio.sleep(2)

        # Get information about the new page
        page_info = await t2_agent.navigate_and_act(
            url="https://en.wikipedia.org/wiki/Python_(programming_language)",
            instruction="Tell me what Wikipedia article we're currently viewing and provide a brief summary",
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Current page info: {page_info}")

    except Exception as e:
        logger.error(f"❌ Navigation demo failed: {e}")
        raise


async def demo_wikipedia_comparison():
    """Demonstrate comparing information from multiple Wikipedia articles."""
    logger.info("⚖️ Demo: Wikipedia Article Comparison")

    t2_agent = T2Agent(llm=llm_client)

    try:
        # Visit first article: Machine Learning
        ml_info = await t2_agent.navigate_and_act(
            url="https://en.wikipedia.org/wiki/Machine_learning",
            instruction="Extract the key definition and main applications of machine learning from this article",
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Machine Learning info: {ml_info}")

        # Visit second article: Deep Learning
        dl_info = await t2_agent.navigate_and_act(
            url="https://en.wikipedia.org/wiki/Deep_learning",
            instruction="Extract the key definition and main applications of deep learning from this article",
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Deep Learning info: {dl_info}")

        # Compare the two
        logger.info("📝 Comparison completed - in a real application, you could now analyze the differences")

    except Exception as e:
        logger.error(f"❌ Comparison demo failed: {e}")
        raise


async def demo_wikipedia_autonomous_research():
    """Demonstrate autonomous research on Wikipedia."""
    logger.info("🤖 Demo: Autonomous Wikipedia Research")

    t2_agent = T2Agent(llm=llm_client)

    try:
        # Create autonomous agent for Wikipedia research
        result = await t2_agent.use_browser(
            instruction="""Go to Wikipedia and research 'Natural Language Processing'. 
            Find the main article, read the introduction, and then explore one related topic 
            by clicking on a relevant link. Summarize what you learned about both topics.""",
            headless=False,
            use_vision=True,
            max_failures=2,
            max_actions_per_step=3,
        )

        logger.info(f"✅ Research completed: {result}")

    except Exception as e:
        logger.error(f"❌ Autonomous research demo failed: {e}")
        raise


async def run_wikipedia_demos():
    """Run all Wikipedia demonstration functions."""
    logger.info("🚀 Starting Wikipedia T2Agent Demo")

    try:
        # Run demos with delays to manage rate limits
        await demo_wikipedia_search()
        await asyncio.sleep(2)  # Brief pause between demos

        await demo_wikipedia_article_extraction()
        await asyncio.sleep(2)

        await demo_wikipedia_navigation()
        await asyncio.sleep(2)

        await demo_wikipedia_comparison()
        await asyncio.sleep(2)

        # Skip autonomous demo initially to avoid rate limits
        logger.info("🤖 Skipping autonomous research demo to manage rate limits")
        logger.info("    To enable it, uncomment the autonomous demo call below")
        # await demo_wikipedia_autonomous_research()

        logger.info("🎉 All Wikipedia demos completed successfully!")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


def main():
    """Main entry point."""
    try:
        asyncio.run(run_wikipedia_demos())
    except KeyboardInterrupt:
        logger.info("👋 Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Demo failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
