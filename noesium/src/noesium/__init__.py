"""
Noesium - A computation-driven cognitive agentic framework

Noesium is a framework for building autonomous AI agents with planning, memory,
tools, and orchestration capabilities. It features an event-sourced multi-agent
kernel architecture emphasizing durability, replayability, and distributed coordination.

Usage Examples:
    # Build a custom agent on the framework
    from noesium import BaseGraphicAgent, FrameworkConfig

    config = FrameworkConfig()

    # LLM client
    from noesium import get_llm_client

    llm = get_llm_client(provider="openai")
    response = await llm.chat("Hello, world!")

    # Configuration
    from noesium import load_config, save_config

    config = load_config()
    config.agent.max_iterations = 50
    save_config(config)

    # Memory systems
    from noesium import MemoryManager, DurableMemory

    memory = MemoryManager()
    await memory.remember("important fact", metadata={"type": "fact"})

    # Browser automation (lazy-loaded)
    from noesium import BrowserUseAgent

    browser = BrowserUseAgent(task="Search for Python tutorials")
"""

__version__ = "0.3.4"

# =============================================================================
# Tier 1: Main Entry Points (Most Common)
# =============================================================================

# Base agents
from noesium.core.agent import (
    BaseAgent,
    BaseGraphicAgent,
)

# Configuration
from noesium.core.config import (
    FrameworkConfig,
    load_config,
    save_config,
)

# Events
from noesium.core.event import (
    EventEnvelope,
    EventStore,
    FileEventStore,
    InMemoryEventStore,
    ProgressCallback,
    ProgressEvent,
    ProgressEventType,
)

# Exceptions - User-facing only
from noesium.core.exceptions import (
    CapabilityError,
    EventError,
    EventValidationError,
    IterationLimitError,
    KernelError,
    MemoryError,
    ModeError,
    NodeExecutionError,
    NoesiumError,
    PlanningError,
    ProviderNotFoundError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
)

# LLM
from noesium.core.llm import get_llm_client

# Memory
from noesium.core.memory import (
    DurableMemory,
    EphemeralMemory,
    MemoryManager,
    SemanticMemory,
)

# Routing
from noesium.core.routing import ModelRouter

# Toolkits - Built-in tool implementations (re-exported for convenience)
# Tools
from noesium.core.toolify import (
    AtomicTool,
    ToolExecutor,
    ToolkitRegistry,
    get_toolkit,
    get_toolkits_map,
)

# Logging
from noesium.core.utils import (
    get_logger,
    setup_logging,
)

# Vector Stores
from noesium.core.vector_store import (
    BaseVectorStore,
    get_vector_store,
)

# Subagents - Reusable agent implementations
from noesium.subagents import (
    AskuraAgent,
    AskuraConfig,
    AskuraResponse,
    AskuraState,
    ResearchState,
    TacitusAgent,
)

# =============================================================================
# Tier 2: Core Systems (Frequently Used)
# =============================================================================


# =============================================================================
# Tier 3: Specialized Subagents
# =============================================================================


# BrowserUseAgent - Lazy import due to heavy dependencies
# Implemented via __getattr__ below

# =============================================================================
# Tier 4: Utilities & Exceptions
# =============================================================================


# =============================================================================
# Lazy Import for BrowserUseAgent
# =============================================================================


def __getattr__(name: str):
    """Lazy import mechanism for BrowserUseAgent to avoid loading heavy dependencies."""
    if name == "BrowserUseAgent":
        try:
            from noesium.subagents.bu import BrowserUseAgent as _BrowserUseAgent

            # Cache in globals to avoid repeated imports
            globals()["BrowserUseAgent"] = _BrowserUseAgent
            return _BrowserUseAgent
        except ImportError as e:
            raise ImportError(
                f"Failed to import BrowserUseAgent. "
                f"Ensure browser-use dependencies are installed: {e}"
            ) from e

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# =============================================================================
# Public API Definition
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # Tier 1: Main Entry Points
    "FrameworkConfig",
    "load_config",
    "save_config",
    "get_llm_client",
    "BaseAgent",
    "BaseGraphicAgent",
    # Tier 2: Core Systems
    "MemoryManager",
    "DurableMemory",
    "EphemeralMemory",
    "SemanticMemory",
    "AtomicTool",
    "ToolExecutor",
    "ToolkitRegistry",
    "get_toolkit",
    "get_toolkits_map",
    "EventEnvelope",
    "EventStore",
    "InMemoryEventStore",
    "FileEventStore",
    "ProgressEvent",
    "ProgressEventType",
    "ProgressCallback",
    "get_vector_store",
    "BaseVectorStore",
    "ModelRouter",
    # Tier 3: Specialized Subagents
    "AskuraAgent",
    "AskuraConfig",
    "AskuraResponse",
    "AskuraState",
    "TacitusAgent",
    "ResearchState",
    "BrowserUseAgent",  # Lazy-loaded
    # Tier 4: Utilities & Exceptions
    "setup_logging",
    "get_logger",
    "NoesiumError",
    "ToolError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "ToolTimeoutError",
    "MemoryError",
    "ProviderNotFoundError",
    "PlanningError",
    "ModeError",
    "IterationLimitError",
    "EventError",
    "EventValidationError",
    "KernelError",
    "NodeExecutionError",
    "CapabilityError",
]
