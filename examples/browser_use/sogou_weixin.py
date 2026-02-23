"""
Browser automation example: Search WeChat articles via Sogou

This example demonstrates using the BrowserUseAgent to search for articles
on WeChat through the Sogou search engine and extract structured results.
"""

import asyncio
import time

from dotenv import load_dotenv

# Noesium-style imports
from noesium.agents.browser_use import BrowserProfile, BrowserUseAgent

load_dotenv()


async def main():
    start_time = time.time()

    query = "甲骨文核心业务"

    task = f"""
    1. 打开https://weixin.sogou.com/
    2. 在搜索框输入：{query}，并点击搜文章
    3. 根据返回的文章列表，获取前两页的搜索结果，并返回每个搜索结果的标题、概要、发布机构、发布时间、文章链接
    4. 以Markdown格式返回
    """

    # Create browser profile configuration
    browser_profile = BrowserProfile(headless=False, enable_default_extensions=False)

    # Create the browser use agent with noesium interface
    agent = BrowserUseAgent(
        browser_profile=browser_profile,
        use_vision=True,
    )

    # Run the agent with the task
    history = await agent.run(
        user_message=task,
        max_steps=50,
    )

    # Extract the final result from the history
    result = history.final_result() if history else "No result available"

    # Print the result
    print("\n" + "=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(result)
    print("=" * 80)

    # Print success status
    if history.is_successful():
        print("\nTask completed successfully!")
    else:
        print("\nTask did not complete successfully.")

    # Print step count
    print(f"Steps taken: {history.number_of_steps()}")

    end_time = time.time()
    print(f"\nTime taken: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
