"""Subagent protocol and runtime interface (RFC-1006 Section 5.5)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Callable, Protocol, runtime_checkable

from .context import SubagentContext
from .descriptor import SubagentDescriptor
from .events import SubagentProgressEvent
from .request import SubagentInvocationRequest, SubagentInvocationResult


@runtime_checkable
class SubagentProtocol(Protocol):
    """Universal interface for all subagents.

    This protocol defines the contract that all subagent implementations must
    follow, regardless of their execution backend (in-process, CLI, remote).

    The protocol supports:
    - Descriptor-based discovery and planning
    - Context-aware initialization with memory sharing
    - Streaming execution with progress events
    - HITL (Human-In-The-Loop) pause/resume semantics
    - Graceful cancellation and cleanup
    """

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        """Return the static descriptor for this subagent type.

        The descriptor provides metadata for discovery, planning, and
        policy enforcement.
        """
        ...

    async def initialize(self, context: SubagentContext) -> None:
        """Initialize the subagent with execution context.

        Called before first execution. Sets up any required resources
        and establishes memory/context sharing with parent.

        Args:
            context: Execution context including session info and shared memory.
        """
        ...

    async def shutdown(self) -> None:
        """Clean up resources and terminate the subagent.

        Must be idempotent - safe to call multiple times.
        """
        ...

    async def execute(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute a task and yield progress events.

        This is the primary execution method. It yields a stream of events
        representing thoughts, tool calls, progress updates, and finally
        the result.

        Args:
            task: The task description/prompt for the subagent.
            **kwargs: Additional arguments for task execution.

        Yields:
            SubagentProgressEvent: Events including START, PROGRESS, THOUGHT,
                TOOL_CALL, TOOL_RESULT, HITL_REQUEST, WARNING, ERROR, END.
        """
        ...

    async def resume(
        self,
        request_id: str,
        input_data: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Resume execution after HITL pause.

        Called when human input is received for a HITL request. Continues
        execution from where it was paused.

        Args:
            request_id: ID of the request that emitted the HITL event.
            input_data: Input received from the human operator.

        Yields:
            SubagentProgressEvent: Continuation of the event stream.
        """
        ...


class BaseSubagentRuntime(ABC):
    """Base class for subagent runtime implementations.

    Provides a concrete base with common functionality for subagent runtimes.
    Subclasses must implement the abstract methods.

    This class adds additional methods beyond the protocol:
    - health() for liveness checking
    - invoke() for non-streaming invocation
    - invoke_stream() for explicit streaming invocation
    - cancel() for request cancellation
    """

    _descriptor: SubagentDescriptor
    _context: SubagentContext | None = None
    _initialized: bool = False

    @property
    def descriptor(self) -> SubagentDescriptor:
        """Return the descriptor for this runtime.

        Falls back to get_descriptor() when no instance-level _descriptor
        has been set (e.g., classes that use a class-level static descriptor).
        """
        if "_descriptor" in self.__dict__:
            return self.__dict__["_descriptor"]
        return self.get_descriptor()

    @property
    def is_initialized(self) -> bool:
        """Check if the runtime has been initialized."""
        return self._initialized

    @classmethod
    @abstractmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        """Return the static descriptor for this subagent type."""
        ...

    async def initialize(self, context: SubagentContext) -> None:
        """Initialize the runtime with execution context.

        Subclasses should call super().initialize(context) first.
        """
        self._context = context
        self._initialized = True

    async def shutdown(self) -> None:
        """Clean up resources. Override in subclasses if needed."""
        self._initialized = False
        self._context = None

    @abstractmethod
    async def health(self) -> bool:
        """Check if the runtime is healthy and ready for invocation.

        Returns:
            True if healthy, False otherwise.
        """
        ...

    async def invoke(
        self,
        request: SubagentInvocationRequest,
    ) -> SubagentInvocationResult:
        """Execute a request and return the final result (non-streaming).

        Default implementation consumes the streaming execute() and
        returns the final result.

        Args:
            request: The invocation request.

        Returns:
            The final result of the invocation.
        """
        final_text = ""
        artifacts: list[dict[str, Any]] = []
        error_code: str | None = None
        error_message: str | None = None

        async for event in self.invoke_stream(request):
            if event.event_type.value == "subagent.end":
                final_text = event.detail or event.summary
            elif event.event_type.value == "subagent.error":
                error_code = event.error_code
                error_message = event.error_message

        if error_code:
            return SubagentInvocationResult.failure_result(
                request_id=request.request_id,
                subagent_id=request.subagent_id,
                error_code=error_code,
                error_message=error_message or "Unknown error",
                partial_text=final_text,
            )

        return SubagentInvocationResult.success_result(
            request_id=request.request_id,
            subagent_id=request.subagent_id,
            final_text=final_text,
            artifacts=artifacts,
        )

    async def invoke_stream(
        self,
        request: SubagentInvocationRequest,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute a request and yield progress events.

        Default implementation wraps execute() with request context.

        Args:
            request: The invocation request.

        Yields:
            SubagentProgressEvent: Progress events from execution.
        """
        async for event in self.execute(request.message, **request.context):
            # Ensure request_id is set on events
            event.request_id = request.request_id
            yield event

    @abstractmethod
    async def execute(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Execute a task and yield progress events.

        This must be implemented by subclasses.
        """
        ...

    async def resume(
        self,
        request_id: str,
        input_data: Any,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Resume execution after HITL pause.

        Default implementation raises NotImplementedError. Override in
        subclasses that support HITL.
        """
        raise NotImplementedError(f"Subagent {self.descriptor.subagent_id} does not support HITL resume")
        yield  # pragma: no cover  # make it an async generator

    async def cancel(self, request_id: str) -> bool:
        """Cancel an in-progress request.

        Default implementation returns False (cancellation not supported).
        Override in subclasses that support cancellation.

        Args:
            request_id: ID of the request to cancel.

        Returns:
            True if cancellation was successful, False otherwise.
        """
        return False


class SubagentProvider:
    """Provider wrapper for registering subagents with CapabilityRegistry.

    Wraps a subagent runtime factory and descriptor for registration with
    the capability registry system. Supports three creation modes:
    - From a class (for entry-point discovery, zero-arg constructor)
    - From a factory callable (for runtime-arg construction)
    - From a pre-built instance (for NoeAgent-specific runtimes)
    """

    def __init__(
        self,
        runtime_class: type[BaseSubagentRuntime],
        descriptor: SubagentDescriptor | None = None,
    ) -> None:
        """Initialize from a runtime class (zero-arg constructor).

        Args:
            runtime_class: The runtime class to instantiate (must have no-arg constructor).
            descriptor: Optional override descriptor. If None, uses
                runtime_class.get_descriptor().
        """
        self._runtime_factory: Callable[[], BaseSubagentRuntime] = runtime_class
        self._descriptor = descriptor or runtime_class.get_descriptor()
        self._instance: BaseSubagentRuntime | None = None

    @classmethod
    def from_instance(cls, runtime: BaseSubagentRuntime) -> SubagentProvider:
        """Create a provider from a pre-built runtime instance.

        Useful when the runtime requires constructor arguments (e.g., NoeAgent-
        specific runtimes that need agent references or config objects).

        Args:
            runtime: A pre-instantiated runtime.

        Returns:
            A SubagentProvider wrapping the runtime.
        """
        provider = cls.__new__(cls)
        provider._runtime_factory = lambda: runtime
        provider._descriptor = runtime.descriptor
        provider._instance = runtime
        return provider

    @classmethod
    def from_factory(
        cls,
        factory: Callable[[], BaseSubagentRuntime],
        descriptor: SubagentDescriptor,
    ) -> SubagentProvider:
        """Create a provider from a callable factory and explicit descriptor.

        Useful when the runtime class cannot be instantiated with zero args
        but the descriptor is known ahead of time.

        Args:
            factory: Callable that returns a BaseSubagentRuntime instance.
            descriptor: The descriptor for this provider.

        Returns:
            A SubagentProvider using the factory.
        """
        provider = cls.__new__(cls)
        provider._runtime_factory = factory
        provider._descriptor = descriptor
        provider._instance = None
        return provider

    @property
    def descriptor(self) -> SubagentDescriptor:
        """Return the descriptor for this provider."""
        return self._descriptor

    @property
    def subagent_id(self) -> str:
        """Return the subagent ID."""
        return self._descriptor.subagent_id

    async def get_runtime(
        self,
        context: SubagentContext | None = None,
    ) -> BaseSubagentRuntime:
        """Get or create the runtime instance.

        Lazily instantiates the runtime on first call using the factory.

        Args:
            context: Optional context to initialize with.

        Returns:
            The runtime instance.
        """
        if self._instance is None:
            self._instance = self._runtime_factory()
            if context:
                await self._instance.initialize(context)

        return self._instance

    async def invoke(
        self,
        request: SubagentInvocationRequest,
        context: SubagentContext | None = None,
    ) -> SubagentInvocationResult:
        """Invoke the subagent with the given request.

        Args:
            request: The invocation request.
            context: Optional context to initialize with.

        Returns:
            The invocation result.
        """
        runtime = await self.get_runtime(context)
        return await runtime.invoke(request)

    async def invoke_stream(
        self,
        request: SubagentInvocationRequest,
        context: SubagentContext | None = None,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Invoke the subagent and yield progress events.

        Args:
            request: The invocation request.
            context: Optional context to initialize with.

        Yields:
            SubagentProgressEvent: Progress events.
        """
        runtime = await self.get_runtime(context)
        async for event in runtime.invoke_stream(request):
            yield event

    async def health(self) -> bool:
        """Check if the subagent is healthy.

        Returns True if not yet instantiated (lazy healthy).
        """
        if self._instance is None:
            return True
        return await self._instance.health()

    async def cleanup(self) -> None:
        """Clean up the runtime instance if it exists."""
        if self._instance is not None:
            await self._instance.shutdown()
            self._instance = None
