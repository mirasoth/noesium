"""
Browser-use Adapters for Noesium

This module provides adapters to bridge between noesium's LLM infrastructure
and the community browser-use repository.

The adapters allow:
- Using noesium's LLM clients with browser-use agents
- Converting between noesium and browser-use message formats
- Integrating browser-use agents with noesium's agent framework

All adapter code is consolidated in this subdirectory.
"""

# Import LLM adapter types and classes
from noesium.agents.browser_use.adapters.llm_adapter import (
    AssistantMessage,
    BaseChatModel,
    BaseMessage,
    ChatInvokeCompletion,
    ChatInvokeUsage,
    ContentImage,
    ContentRefusal,
    ContentText,
    ImageURL,
    ModelProviderError,
    ModelRateLimitError,
    NoesiumLLMAdapter,
    SystemMessage,
    UserMessage,
    create_llm_adapter,
)


# Lazy import agent adapter to avoid circular imports
# (agent_adapter imports agent.service which imports from llm_adapter)
def __getattr__(name: str):
    if name in ("NoesiumAgentAdapter", "create_agent_adapter"):
        from noesium.agents.browser_use.adapters import agent_adapter

        return getattr(agent_adapter, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # LLM Adapter types
    "ChatInvokeUsage",
    "ChatInvokeCompletion",
    "BaseChatModel",
    "ModelProviderError",
    "ModelRateLimitError",
    "ImageURL",
    # Message types
    "BaseMessage",
    "UserMessage",
    "SystemMessage",
    "AssistantMessage",
    "ContentText",
    "ContentRefusal",
    "ContentImage",
    # LLM Adapter
    "NoesiumLLMAdapter",
    "create_llm_adapter",
    # Agent Adapter (lazy loaded)
    "NoesiumAgentAdapter",
    "create_agent_adapter",
]
