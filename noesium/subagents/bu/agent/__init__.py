"""
BrowserUseAgent - Browser automation agent for noesium.

This module provides a wrapper around the browser-use Agent class
that integrates with noesium's architecture.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any, Generic, TypeVar

from noesium.core.agent import BaseAgent
from noesium.core.llm import BaseLLMClient
from noesium.core.utils.logging import get_logger

from ..browser.profile import BrowserProfile
from .service import Agent
from .views import AgentHistoryList

T = TypeVar("T")

# Base directory for browser-use session data
_NOEAGENT_DIR = Path.home() / ".noeagent"
_BROWSER_USE_SESSIONS_DIR = _NOEAGENT_DIR / "browser-use-sessions"


def _create_session_dir(session_id: str) -> Path:
    """Create an isolated session directory for browser-use.

    Args:
        session_id: Unique identifier for the session.

    Returns:
        Path to the created session directory.
    """
    session_dir = _BROWSER_USE_SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (session_dir / "user-data").mkdir(exist_ok=True)
    (session_dir / "downloads").mkdir(exist_ok=True)

    return session_dir


class BrowserUseAgent(BaseAgent, Generic[T]):
    """
    Browser automation agent that wraps the browser-use Agent class.

    This agent provides browser automation capabilities through a natural
    language interface, allowing users to control web browsers to perform
    tasks like navigation, form filling, and content extraction.

    Each session uses an isolated directory under ~/.noeagent/browser-use-sessions/
    to store browser profile data, downloads, and other temporary files.
    """

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        browser_profile: BrowserProfile | None = None,
        use_vision: bool = True,
        headless: bool = True,
        session_id: str | None = None,
        cleanup_on_close: bool = True,
        **kwargs,
    ):
        """Initialize the BrowserUseAgent.

        Args:
            llm: LLM client to use. If None, uses default noesium LLM client.
            browser_profile: Browser configuration profile. If None, creates one with isolated session dir.
            use_vision: Whether to use vision capabilities.
            headless: Whether to run browser in headless mode (default: True).
            session_id: Unique session identifier. If None, generates one automatically.
            cleanup_on_close: Whether to delete session directory on close (default: True).
            **kwargs: Additional arguments passed to the underlying Agent.
        """
        super().__init__(llm_provider="openai", model_name=None)  # Will be overridden

        if llm is None:
            from noesium.core.llm import get_llm_client

            llm = get_llm_client(structured_output=True)

        # Generate session ID if not provided
        if session_id is None:
            from uuid_extensions import uuid7str

            session_id = uuid7str()[:12]  # Short ID for directory names

        self._session_id = session_id
        self._cleanup_on_close = cleanup_on_close
        self._session_dir: Path | None = None

        # Create isolated session directory
        self._session_dir = _create_session_dir(session_id)

        # Create default browser profile with isolated session directory
        if browser_profile is None:
            browser_profile = BrowserProfile(
                headless=headless,
                user_data_dir=str(self._session_dir / "user-data"),
                downloads_path=str(self._session_dir / "downloads"),
            )
        elif browser_profile.headless is None:
            # Ensure headless is set if profile was provided but headless is None
            browser_profile.headless = headless
            # Still set isolated directories if not already set
            if browser_profile.user_data_dir is None:
                browser_profile.user_data_dir = str(self._session_dir / "user-data")
            if browser_profile.downloads_path is None:
                browser_profile.downloads_path = str(self._session_dir / "downloads")

        self.browser_profile = browser_profile
        self.use_vision = use_vision
        self._llm_client = llm
        self._underlying_agent: Agent | None = None

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id

    @property
    def session_dir(self) -> Path | None:
        """Get the session directory path."""
        return self._session_dir

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
        from ..adapters.llm_adapter import BaseChatModel

        if self._underlying_agent is None:
            self._underlying_agent = Agent(
                task=user_message,
                llm=BaseChatModel(self._llm_client),
                browser_profile=self.browser_profile,
                use_vision=self.use_vision,
            )

        return await self._underlying_agent.run(max_steps=max_steps)

    async def close(self) -> None:
        """Close the browser session and optionally clean up session directory."""
        if self._underlying_agent is not None:
            # The underlying agent should have a close/cleanup method
            # For now, we just clear the reference
            self._underlying_agent = None

        if self._cleanup_on_close and self._session_dir is not None:
            try:
                shutil.rmtree(self._session_dir, ignore_errors=True)
                self.logger.debug("Cleaned up session directory: %s", self._session_dir)
            except Exception as e:
                self.logger.warning("Failed to clean up session directory: %s", e)
            finally:
                self._session_dir = None

    async def __aenter__(self) -> "BrowserUseAgent[T]":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup session."""
        await self.close()

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
