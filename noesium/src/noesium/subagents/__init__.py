"""Built-in subagents for the Noesium framework.

This module provides access to reusable subagent implementations. Each subagent
inherits from core base classes and can be used independently or as part of
larger agent applications.

Available Subagents:
    - AskuraAgent: General-purpose conversation agent
    - TacitusAgent: Research agent with iterative query generation
    - BrowserUseAgent: Web automation agent (lazy-loaded due to heavy dependencies)
    - PlanAgent: General-purpose planning agent for domain-agnostic plans
    - ExploreAgent: Exploration agent for gathering information from diverse sources
    - DavinciAgent: Scientific research agent (placeholder, lazy-loaded)

Usage:
    from noesium.subagents import AskuraAgent, TacitusAgent, PlanAgent, ExploreAgent

    # AskuraAgent for conversations
    agent = AskuraAgent()
    response = agent.start_conversation("user_123", "Hello!")

    # TacitusAgent for research
    researcher = TacitusAgent()
    result = await researcher.research("What is quantum computing?")

    # PlanAgent for creating implementation plans
    planner = PlanAgent()
    plan = await planner.run("Plan how to implement a REST API")

    # ExploreAgent for gathering information
    explorer = ExploreAgent()
    findings = await explorer.run("Explore the authentication module")
"""

# Subagent names / types (defined here, not in core)
SUBAGENT_ASKURA = "askura"
SUBAGENT_BROWSER_USE = "browser_use"
SUBAGENT_CLAUDE = "claude"
SUBAGENT_TACITUS = "tacitus"
SUBAGENT_PLAN = "plan"
SUBAGENT_EXPLORE = "explore"
SUBAGENT_DAVINCI = "davinci"

from noesium.subagents.askura import (
    AskuraAgent,
    AskuraConfig,
    AskuraResponse,
    AskuraState,
)
from noesium.subagents.explore import (
    ExploreAgent,
    ExploreResult,
    ExploreState,
    Finding,
    ReflectionResult,
    Source,
)
from noesium.subagents.plan import (
    ContextEvaluation,
    DetailedPlan,
    PlanAgent,
    PlanState,
    PlanStep,
)
from noesium.subagents.tacitus import ResearchState, TacitusAgent

__all__ = [
    # Subagent names
    "SUBAGENT_ASKURA",
    "SUBAGENT_BROWSER_USE",
    "SUBAGENT_CLAUDE",
    "SUBAGENT_TACITUS",
    "SUBAGENT_PLAN",
    "SUBAGENT_EXPLORE",
    "SUBAGENT_DAVINCI",
    # Subagent classes
    "AskuraAgent",
    "AskuraConfig",
    "AskuraResponse",
    "AskuraState",
    "TacitusAgent",
    "ResearchState",
    "PlanAgent",
    "PlanState",
    "PlanStep",
    "DetailedPlan",
    "ContextEvaluation",
    "ExploreAgent",
    "ExploreState",
    "ExploreResult",
    "Finding",
    "Source",
    "ReflectionResult",
    "BrowserUseAgent",  # Lazy-loaded
    "DavinciAgent",  # Lazy-loaded
]


# Lazy import for BrowserUseAgent and DavinciAgent to avoid loading heavy dependencies
def __getattr__(name: str):
    """Lazy import mechanism for BrowserUseAgent and DavinciAgent."""
    if name == "BrowserUseAgent":
        try:
            from noesium.subagents.bu import BrowserUseAgent as _BrowserUseAgent

            globals()["BrowserUseAgent"] = _BrowserUseAgent
            return _BrowserUseAgent
        except ImportError as e:
            raise ImportError(
                f"Failed to import BrowserUseAgent. " f"Ensure browser-use dependencies are installed: {e}"
            ) from e

    if name == "DavinciAgent":
        try:
            from noesium.subagents.davinci import DavinciAgent as _DavinciAgent

            globals()["DavinciAgent"] = _DavinciAgent
            return _DavinciAgent
        except ImportError as e:
            raise ImportError(f"Failed to import DavinciAgent: {e}") from e

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
