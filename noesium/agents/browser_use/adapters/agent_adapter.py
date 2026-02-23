"""
Agent Adapter for Noesium to browser-use

This module provides adapters to integrate browser-use agents with noesium's agent framework.
"""

import asyncio
from typing import Any, Generic, TypeVar

from noesium.agents.browser_use import BrowserProfile
from noesium.agents.browser_use.adapters.llm_adapter import create_llm_adapter
from noesium.agents.browser_use.agent.service import Agent
from noesium.agents.browser_use.agent.views import AgentHistoryList
from noesium.core.agent import BaseAgent
from noesium.core.llm import BaseLLMClient
from noesium.core.utils.logging import get_logger

T = TypeVar("T")


class NoesiumAgentAdapter(BaseAgent, Generic[T]):
    """
    Adapter that wraps browser-use Agent for use in noesium's agent framework.

    This adapter provides a noesium-compatible interface to browser-use's
    browser automation capabilities.
    """

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        browser_profile: BrowserProfile | None = None,
        use_vision: bool = True,
        **kwargs,
    ):
        """
        Initialize the adapter.

        Args:
            llm: LLM client to use. If None, uses default noesium LLM client.
            browser_profile: Browser configuration profile.
            use_vision: Whether to use vision capabilities.
            **kwargs: Additional arguments passed to the underlying Agent.
        """
        super().__init__(llm_provider="openai", model_name=None)

        if llm is None:
            from noesium.core.llm import get_llm_client

            llm = get_llm_client(structured_output=True)

        self.browser_profile = browser_profile or BrowserProfile()
        self.use_vision = use_vision
        self._llm_client = llm
        self._underlying_agent: Agent | None = None

    _logger = None

    @property
    def logger(self):
        """Get the logger instance."""
        if self._logger is None:
            self._logger = get_logger(self.__class__.__name__)
        return self._logger

    @logger.setter
    def logger(self, value):
        """Set the logger instance (for parent class compatibility)."""
        self._logger = value

    async def run(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        config: Any = None,
        max_steps: int = 25,
    ) -> AgentHistoryList[T]:
        """
        Run the browser automation agent.

        Args:
            user_message: The task description in natural language.
            context: Optional context dictionary (ignored in browser_use).
            config: Optional config object (ignored in browser_use).
            max_steps: Maximum number of steps to take.

        Returns:
            AgentHistoryList containing the execution history and results.
        """
        if self._underlying_agent is None:
            self._underlying_agent = Agent(
                task=user_message,
                llm=create_llm_adapter(self._llm_client),
                browser_profile=self.browser_profile,
                use_vision=self.use_vision,
            )

        return await self._underlying_agent.run(max_steps=max_steps)

    def run_sync(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        config: Any = None,
        max_steps: int = 25,
    ) -> AgentHistoryList[T]:
        """
        Synchronous wrapper around run() for easier usage without asyncio.

        Args:
            user_message: The task description in natural language.
            context: Optional context dictionary (ignored in browser_use).
            config: Optional config object (ignored in browser_use).
            max_steps: Maximum number of steps to take.

        Returns:
            AgentHistoryList containing the execution history and results.
        """
        return asyncio.run(self.run(user_message, context, config, max_steps))


def create_agent_adapter(
    llm: BaseLLMClient | None = None,
    browser_profile: BrowserProfile | None = None,
    use_vision: bool = True,
    **kwargs,
) -> NoesiumAgentAdapter:
    """
    Create a noesium-compatible agent adapter from browser-use Agent.

    Args:
        llm: A noesium BaseLLMClient instance
        browser_profile: Browser configuration profile
        use_vision: Whether to use vision capabilities
        **kwargs: Additional arguments

    Returns:
        NoesiumAgentAdapter instance
    """
    return NoesiumAgentAdapter(llm, browser_profile, use_vision, **kwargs)
