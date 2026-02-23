"""
Browser automation example: Find stock prices and create CSV

This example demonstrates using the BrowserUseAgent to find historical stock
prices for multiple companies and create a CSV file with the results.
"""

import asyncio
import time

from dotenv import load_dotenv

# Noesium-style imports
from noesium.agents.browser_use import BrowserProfile, BrowserUseAgent

load_dotenv()


async def main():
    start_time = time.time()

    task = """
    Find historical stock price of companies Alibaba and Google for the last 3 months.
    Then, make me a CSV file with 2 columns: company name, stock price.
    """

    # Create browser profile configuration
    browser_profile = BrowserProfile(
        headless=False,
    )

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
