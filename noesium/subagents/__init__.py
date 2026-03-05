"""Built-in subagents for the Noesium framework.

This module provides access to reusable subagent implementations. Each subagent
inherits from core base classes and can be used independently or as part of
larger agent applications.

Available Subagents:
    - AskuraAgent: General-purpose conversation agent
    - TacitusAgent: Research agent with iterative query generation
    - BrowserUseAgent: Web automation agent (lazy-loaded due to heavy dependencies)

Usage:
    from noesium.subagents import AskuraAgent, TacitusAgent

    # AskuraAgent for conversations
    agent = AskuraAgent()
    response = agent.start_conversation("user_123", "Hello!")

    # TacitusAgent for research
    researcher = TacitusAgent()
    result = await researcher.research("What is quantum computing?")
"""

# Subagent names / types (defined here, not in core)
SUBAGENT_ASKURA = "askura"
SUBAGENT_BROWSER_USE = "browser_use"
SUBAGENT_CLAUDE = "claude"
SUBAGENT_TACITUS = "tacitus"

from noesium.subagents.askura import (
    AskuraAgent,
    AskuraConfig,
    AskuraResponse,
    AskuraState,
)
from noesium.subagents.tacitus import ResearchState, TacitusAgent

__all__ = [
    # Subagent names
    "SUBAGENT_ASKURA",
    "SUBAGENT_BROWSER_USE",
    "SUBAGENT_CLAUDE",
    "SUBAGENT_TACITUS",
    # Subagent classes
    "AskuraAgent",
    "AskuraConfig",
    "AskuraResponse",
    "AskuraState",
    "TacitusAgent",
    "ResearchState",
    "BrowserUseAgent",  # Lazy-loaded
]


# Lazy import for BrowserUseAgent to avoid loading heavy dependencies
def __getattr__(name: str):
    """Lazy import mechanism for BrowserUseAgent."""
    if name == "BrowserUseAgent":
        try:
            from noesium.subagents.bu import BrowserUseAgent as _BrowserUseAgent

            globals()["BrowserUseAgent"] = _BrowserUseAgent
            return _BrowserUseAgent
        except ImportError as e:
            raise ImportError(
                f"Failed to import BrowserUseAgent. " f"Ensure browser-use dependencies are installed: {e}"
            ) from e

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
