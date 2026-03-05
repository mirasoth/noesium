"""
BrowserUseAgent - Browser automation agent for noesium.

This module provides a wrapper around the browser-use Agent class
that integrates with noesium's architecture.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any, AsyncGenerator, Generic, TypeVar

from noesium.core.agent import BaseAgent
from noesium.core.llm import BaseLLMClient
from noesium.core.utils.logging import get_logger

from ..browser.profile import BrowserProfile
from ..config import DEFAULT_HEADLESS
from .service import Agent
from .views import AgentHistoryList


# Lazy import for ProgressEvent to avoid circular imports
def _get_progress_types():
    """Lazy import progress types."""
    from noesium.core.event import ProgressEvent, ProgressEventType

    return ProgressEvent, ProgressEventType


T = TypeVar("T")

# Fallback base directory when no parent session dir is provided (framework default)
from noesium.core.consts import NOESIUM_HOME

_BROWSER_USE_SESSIONS_DIR = NOESIUM_HOME / "browser-use-sessions"


def _create_session_dir(session_id: str, *, parent_session_dir: str | Path | None = None) -> Path:
    """Create an isolated session directory for browser-use.

    When ``parent_session_dir`` is supplied (the caller's session directory),
    the browser-use data is placed under ``<parent_session_dir>/browser-use/``.
    Otherwise falls back to ``NOESIUM_HOME/browser-use-sessions/<session_id>/``.

    Args:
        session_id: Unique identifier for the session.
        parent_session_dir: Caller's session directory (preferred).

    Returns:
        Path to the created session directory.
    """
    if parent_session_dir is not None:
        session_dir = Path(parent_session_dir) / "browser-use"
    else:
        session_dir = _BROWSER_USE_SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    (session_dir / "user-data").mkdir(exist_ok=True)
    (session_dir / "downloads").mkdir(exist_ok=True)

    return session_dir


class BrowserUseAgent(BaseAgent, Generic[T]):
    """
    Browser automation agent that wraps the browser-use Agent class.

    This agent provides browser automation capabilities through a natural
    language interface, allowing users to control web browsers to perform
    tasks like navigation, form filling, and content extraction.

    Each session uses an isolated directory under the caller's session dir
    or NOESIUM_HOME/browser-use-sessions/ to store browser profile data.
    """

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        browser_profile: BrowserProfile | None = None,
        use_vision: bool = True,
        headless: bool = DEFAULT_HEADLESS,
        session_id: str | None = None,
        cleanup_on_close: bool = True,
        parent_session_dir: str | Path | None = None,
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
            parent_session_dir: Caller's session directory. When provided, BU temp data is
                placed under ``<parent_session_dir>/browser-use/`` for session isolation.
            **kwargs: Additional arguments passed to the underlying Agent.
        """
        super().__init__(llm_provider="openai", model_name=None)  # Will be overridden

        if llm is None:
            from noesium.core.llm import get_llm_client

            llm = get_llm_client(structured_output=True)

        if session_id is None:
            from uuid_extensions import uuid7str

            session_id = uuid7str()[:12]

        self._session_id = session_id
        self._cleanup_on_close = cleanup_on_close
        self._session_dir: Path | None = None

        self._session_dir = _create_session_dir(session_id, parent_session_dir=parent_session_dir)

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

    async def astream_progress(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        config: Any = None,
        max_steps: int = 25,
    ) -> AsyncGenerator[Any, None]:
        """Stream progress events during browser automation.

        This method yields ProgressEvent objects compatible with the core
        progress system, allowing real-time visibility into browser actions.

        Events are emitted live via an async step callback so each step's
        Eval / Memory / Next-goal / Action information is surfaced as it
        happens, rather than being reconstructed from history post-run.

        Args:
            user_message: The task description in natural language.
            context: Optional context dictionary (ignored in browser_use).
            config: Optional config object (ignored in browser_use).
            max_steps: Maximum number of steps to take.

        Yields:
            ProgressEvent: Events describing browser automation progress.

        Event Sequence:
            1. SESSION_START - Browser session initialized
            2. PLAN_CREATED - Dynamic plan (up to max_steps)
            3. THINKING - Browser launch notification
            4. Per step (live, via async callback):
               - STEP_START   summary = "Step N: <next_goal>"
                              detail  = Eval / Memory / Next goal / Action
               - TOOL_START   summary = <action description>
            5. FINAL_ANSWER - Task result
            6. SESSION_END - Cleanup complete
        """
        import asyncio

        ProgressEvent, ProgressEventType = _get_progress_types()
        from uuid_extensions import uuid7str

        session_id = uuid7str()

        # Sentinel object placed into the queue when agent.run() finishes.
        _DONE = object()
        step_queue: asyncio.Queue = asyncio.Queue()

        # Yield SESSION_START
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            summary=f"Browser task: {user_message[:60]}",
        )

        # Yield PLAN_CREATED (browser steps are dynamic)
        yield ProgressEvent(
            type=ProgressEventType.PLAN_CREATED,
            session_id=session_id,
            summary=f"Browser automation: up to {max_steps} steps",
            plan_snapshot={
                "steps": [],
                "goal": user_message,
                "max_steps": max_steps,
            },
        )

        async def on_step(browser_state: Any, model_output: Any, step_num: int) -> None:
            """Async step callback: emit live per-step progress events."""
            eval_text = ""
            memory_text = ""
            next_goal = ""
            action_desc = ""

            if model_output and hasattr(model_output, "current_state"):
                cs = model_output.current_state
                eval_text = getattr(cs, "evaluation_previous_goal", "") or ""
                memory_text = getattr(cs, "memory", "") or ""
                next_goal = getattr(cs, "next_goal", "") or ""

            if model_output and hasattr(model_output, "action") and model_output.action:
                action_desc = self._describe_action_from_output(model_output)

            summary = f"Step {step_num}"
            if next_goal:
                summary = f"Step {step_num}: {next_goal[:80]}"
            elif action_desc:
                summary = f"Step {step_num}: {action_desc[:80]}"

            detail_parts = []
            if eval_text:
                detail_parts.append(f"Eval: {eval_text}")
            if memory_text:
                detail_parts.append(f"Memory: {memory_text}")
            if next_goal:
                detail_parts.append(f"Next goal: {next_goal}")
            if action_desc:
                detail_parts.append(f"Action: {action_desc}")
            detail = "\n".join(detail_parts) or None

            # STEP_START carries the rich eval/memory/next_goal detail
            await step_queue.put(
                ProgressEvent(
                    type=ProgressEventType.STEP_START,
                    session_id=session_id,
                    step_index=step_num,
                    summary=summary,
                    detail=detail,
                )
            )

            # Emit a TOOL_START for the chosen browser action
            if action_desc:
                await step_queue.put(
                    ProgressEvent(
                        type=ProgressEventType.TOOL_START,
                        session_id=session_id,
                        tool_name="browser_action",
                        summary=action_desc,
                        detail=detail,
                    )
                )

        # Create underlying agent with the async step callback
        from ..adapters.llm_adapter import BaseChatModel

        try:
            agent = Agent(
                task=user_message,
                llm=BaseChatModel(self._llm_client),
                browser_profile=self.browser_profile,
                use_vision=self.use_vision,
                register_new_step_callback=on_step,
            )

            # Yield THINKING before starting - browser launch happens here
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id=session_id,
                summary="Launching browser... (this may take up to 30s)",
            )

            # Run agent.run() concurrently so we can drain the step queue live.
            async def _run_agent() -> Any:
                try:
                    return await agent.run(max_steps=max_steps)
                finally:
                    await step_queue.put(_DONE)

            run_task = asyncio.ensure_future(_run_agent())

            # Drain step events until the sentinel arrives
            while True:
                item = await step_queue.get()
                if item is _DONE:
                    break
                yield item

            # Collect the result (re-raises any agent exception)
            result = await run_task
            self._last_result = result

            # Yield final answer
            final_result = result.final_result() if result else None
            yield ProgressEvent(
                type=ProgressEventType.FINAL_ANSWER,
                session_id=session_id,
                text=final_result or "Task completed (no text result)",
                summary="Browser task completed",
            )

        except Exception as e:
            self.logger.error(f"Browser task failed: {e}")
            yield ProgressEvent(
                type=ProgressEventType.ERROR,
                session_id=session_id,
                error=str(e),
                summary=f"Browser task failed: {str(e)[:60]}",
            )
            raise

        finally:
            # Yield SESSION_END
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )

    def _describe_action_from_output(self, model_output) -> str:
        """Generate human-readable description from model output."""
        if not model_output:
            return "Unknown action"

        action = getattr(model_output, "action", None)
        if not action:
            return "Processing..."

        # Get action name and parameters
        action_name = type(action).__name__.lower()

        # Map action types to descriptions
        action_descriptions = {
            "clickaction": "👆 Clicking element",
            "inputtextaction": "⌨️ Typing text",
            "gotourlaction": "→ Navigating",
            "scrollaction": "📜 Scrolling",
            "extractcontentaction": "📄 Extracting content",
            "downloadaction": "📥 Downloading",
            "switchtabaction": "🔄 Switching tab",
            "doneaction": "✓ Task complete",
            "searchaction": "🔍 Searching",
        }

        # Get base description
        base_desc = "🔧 Browser action"
        for key, desc in action_descriptions.items():
            if key.lower() in action_name:
                base_desc = desc
                break

        # Add context if available
        context = ""
        if hasattr(action, "url") and action.url:
            context = f": {action.url[:40]}"
        elif hasattr(action, "text") and action.text:
            text_preview = str(action.text)[:30]
            context = f": {text_preview}..."
        elif hasattr(action, "index") and isinstance(getattr(action, "index", None), int):
            context = f" (element {action.index})"
        elif hasattr(action, "query") and action.query:
            context = f": {action.query[:40]}"

        return f"{base_desc}{context}"

    def _describe_result(self, result) -> str:
        """Generate description from action result."""
        if not result:
            return "Done"

        # Handle list of results
        if isinstance(result, list) and result:
            result = result[-1]

        # Check for common result attributes
        if hasattr(result, "extracted_content") and result.extracted_content:
            return f"Extracted: {result.extracted_content[:50]}..."
        if hasattr(result, "is_done") and result.is_done:
            return "Task completed successfully"
        if hasattr(result, "error") and result.error:
            return f"Error: {result.error[:50]}"

        return "Action completed"


__all__ = ["BrowserUseAgent", "Agent", "AgentHistoryList", "BrowserProfile"]
