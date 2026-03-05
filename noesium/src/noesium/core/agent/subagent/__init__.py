"""Subagent interface module for the core agent framework (RFC-1006).

This module provides a general-purpose, framework-agnostic interface for
heterogeneous subagents. It is intentionally independent of any specific
agent implementation.

Key components:
- SubagentDescriptor: Static metadata for discovery and planning
- SubagentContext: Execution context with memory sharing
- SubagentProgressEvent: Streaming event protocol
- SubagentInvocationRequest/Result: Request/response contracts
- SubagentProtocol: Universal interface for all subagents
- BaseSubagentRuntime: Base class for runtime implementations
- SubagentProvider: Registration wrapper (supports class, factory, or instance)
- SubagentManager: Selection, invocation, and lifecycle management
- SubagentLoader: Dynamic discovery via entry points
"""

from .context import SubagentContext
from .descriptor import (
    BackendType,
    CostHint,
    LatencyHint,
    SubagentDescriptor,
    SubagentRoutingPolicy,
)
from .events import (
    SubagentErrorCode,
    SubagentEventType,
    SubagentProgressEvent,
)
from .manager import (
    SubagentLoader,
    SubagentManager,
    SubagentQuery,
)
from .protocol import (
    BaseSubagentRuntime,
    SubagentProtocol,
    SubagentProvider,
)
from .request import (
    SubagentInvocationRequest,
    SubagentInvocationResult,
)

__all__ = [
    # Context
    "SubagentContext",
    # Descriptor
    "BackendType",
    "CostHint",
    "LatencyHint",
    "SubagentDescriptor",
    "SubagentRoutingPolicy",
    # Events
    "SubagentErrorCode",
    "SubagentEventType",
    "SubagentProgressEvent",
    # Manager
    "SubagentLoader",
    "SubagentManager",
    "SubagentQuery",
    # Protocol
    "BaseSubagentRuntime",
    "SubagentProtocol",
    "SubagentProvider",
    # Request/Result
    "SubagentInvocationRequest",
    "SubagentInvocationResult",
]
