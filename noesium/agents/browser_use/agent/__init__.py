"""
BrowserUseAgent - Browser automation agent for noesium.

This module provides a wrapper around the browser-use Agent class
that integrates with noesium's architecture.
"""

import asyncio
import logging
from typing import Any, Generic, TypeVar

from noesium.core.agent import BaseAgent
from noesium.core.llm import BaseLLMClient
from noesium.core.utils.logging import get_logger

from ..browser.profile import BrowserProfile
from .service import Agent
from .views import AgentHistoryList

T = TypeVar("T")


class BrowserUseAgent(BaseAgent, Generic[T]):
    """
    Browser automation agent that wraps the browser-use Agent class.

    This agent provides browser automation capabilities through a natural
    language interface, allowing users to control web browsers to perform
    tasks like navigation, form filling, and content extraction.
    """

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        browser_profile: BrowserProfile | None = None,
        use_vision: bool = True,
        **kwargs,
    ):
        """Initialize the BrowserUseAgent.

        Args:
            llm: LLM client to use. If None, uses default noesium LLM client.
            browser_profile: Browser configuration profile.
            use_vision: Whether to use vision capabilities.
            **kwargs: Additional arguments passed to the underlying Agent.
        """
        super().__init__(llm_provider="openai", model_name=None)  # Will be overridden

        if llm is None:
            from noesium.core.llm import get_llm_client

            llm = get_llm_client(structured_output=True)

        self.browser_profile = browser_profile or BrowserProfile()
        self.use_vision = use_vision
        self._llm_client = llm
        self._underlying_agent: Agent | None = None

    _logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        if self._logger is None:
            self._logger = get_logger(self.__class__.__name__)
        return self._logger

    @logger.setter
    def logger(self, value: logging.Logger) -> None:
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
        from ..llm_adapter import BaseChatModel

        if self._underlying_agent is None:
            self._underlying_agent = Agent(
                task=user_message,
                llm=BaseChatModel(self._llm_client),
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


__all__ = ["BrowserUseAgent", "Agent", "AgentHistoryList", "BrowserProfile"]
