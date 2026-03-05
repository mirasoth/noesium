"""Subagent manager for selection, invocation, and lifecycle (RFC-1006 Section 4)."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from .context import SubagentContext
from .descriptor import SubagentDescriptor, SubagentRoutingPolicy
from .events import SubagentErrorCode, SubagentProgressEvent
from .protocol import BaseSubagentRuntime, SubagentProvider
from .request import SubagentInvocationRequest, SubagentInvocationResult

logger = logging.getLogger(__name__)


@dataclass
class SubagentQuery:
    """Query criteria for subagent selection."""

    task_type: str | None = None
    keywords: list[str] = field(default_factory=list)
    exclude_explicit_only: bool = True
    max_cost: str | None = None
    max_latency: str | None = None


class SubagentLoader:
    """Dynamic subagent discovery via entry points and config.

    Implements RFC-1006 Section 6.3 dynamic discovery.
    """

    @staticmethod
    def discover_subagents() -> list[type[BaseSubagentRuntime]]:
        """Discover all registered subagents via entry points.

        Returns:
            List of subagent runtime classes.
        """
        try:
            from importlib.metadata import entry_points

            subagents: list[type[BaseSubagentRuntime]] = []
            eps = entry_points(group="noesium.subagents")

            for ep in eps:
                try:
                    subagent_class = ep.load()
                    if isinstance(subagent_class, type) and issubclass(subagent_class, BaseSubagentRuntime):
                        subagents.append(subagent_class)
                    else:
                        logger.warning(
                            "Entry point %s did not load a BaseSubagentRuntime subclass",
                            ep.name,
                        )
                except Exception as e:
                    logger.warning("Failed to load subagent %s: %s", ep.name, e)

            return subagents
        except Exception as e:
            logger.warning("Failed to discover subagents via entry points: %s", e)
            return []

    @staticmethod
    def discover_from_config(config: dict[str, Any]) -> list[type[BaseSubagentRuntime]]:
        """Fallback: discover subagents from config-driven module paths.

        Args:
            config: Configuration dict with 'subagent_modules' key.

        Returns:
            List of subagent runtime classes.
        """
        subagents: list[type[BaseSubagentRuntime]] = []

        for module_path in config.get("subagent_modules", []):
            try:
                module = importlib.import_module(module_path)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseSubagentRuntime) and obj is not BaseSubagentRuntime:
                        subagents.append(obj)
            except Exception as e:
                logger.warning("Failed to load subagent module %s: %s", module_path, e)

        return subagents


class SubagentManager:
    """Manager for subagent selection, invocation, and lifecycle.

    Integrates with CapabilityRegistry for discovery while providing
    subagent-specific invocation semantics.
    """

    def __init__(
        self,
        registry: Any | None = None,
        default_timeout_s: float = 300.0,
        max_concurrent: int = 5,
    ) -> None:
        """Initialize the manager.

        Args:
            registry: Optional CapabilityRegistry for discovery integration.
            default_timeout_s: Default timeout for invocations.
            max_concurrent: Maximum concurrent invocations.
        """
        self._registry = registry
        self._providers: dict[str, SubagentProvider] = {}
        self._policies: dict[str, SubagentRoutingPolicy] = {}
        self._default_timeout_s = default_timeout_s
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_requests: dict[str, asyncio.Task[Any]] = {}

    def register(
        self,
        provider: SubagentProvider,
        policy: SubagentRoutingPolicy | None = None,
    ) -> None:
        """Register a subagent provider.

        Args:
            provider: The provider to register.
            policy: Optional routing policy. If None, uses default policy.
        """
        subagent_id = provider.subagent_id
        self._providers[subagent_id] = provider
        self._policies[subagent_id] = policy or SubagentRoutingPolicy()
        logger.info("Registered subagent: %s", subagent_id)

    def register_runtime_class(
        self,
        runtime_class: type[BaseSubagentRuntime],
        policy: SubagentRoutingPolicy | None = None,
    ) -> None:
        """Register a subagent runtime class.

        Convenience method that creates a provider from the class.

        Args:
            runtime_class: The runtime class to register.
            policy: Optional routing policy.
        """
        provider = SubagentProvider(runtime_class)
        self.register(provider, policy)

    def unregister(self, subagent_id: str) -> bool:
        """Unregister a subagent provider.

        Args:
            subagent_id: ID of the subagent to unregister.

        Returns:
            True if unregistered, False if not found.
        """
        if subagent_id in self._providers:
            del self._providers[subagent_id]
            self._policies.pop(subagent_id, None)
            logger.info("Unregistered subagent: %s", subagent_id)
            return True
        return False

    def get_provider(self, subagent_id: str) -> SubagentProvider | None:
        """Get a provider by subagent ID.

        Args:
            subagent_id: ID of the subagent.

        Returns:
            The provider, or None if not found.
        """
        return self._providers.get(subagent_id)

    def get_policy(self, subagent_id: str) -> SubagentRoutingPolicy | None:
        """Get the routing policy for a subagent.

        Args:
            subagent_id: ID of the subagent.

        Returns:
            The policy, or None if not found.
        """
        return self._policies.get(subagent_id)

    def list_providers(self) -> list[SubagentProvider]:
        """List all registered providers.

        Returns:
            List of providers.
        """
        return list(self._providers.values())

    def list_descriptors(self) -> list[SubagentDescriptor]:
        """List all registered descriptors.

        Returns:
            List of descriptors.
        """
        return [p.descriptor for p in self._providers.values()]

    def select(
        self,
        query: SubagentQuery,
        context: SubagentContext | None = None,
    ) -> list[SubagentProvider]:
        """Select subagents matching the query criteria.

        Args:
            query: Selection criteria.
            context: Optional context for policy checks.

        Returns:
            List of matching providers, sorted by relevance.
        """
        matches: list[SubagentProvider] = []

        for subagent_id, provider in self._providers.items():
            descriptor = provider.descriptor
            policy = self._policies.get(subagent_id, SubagentRoutingPolicy())

            # Check explicit command requirement
            if query.exclude_explicit_only and policy.requires_explicit_command:
                continue

            # Check task type
            if query.task_type and not descriptor.matches_task_type(query.task_type):
                continue

            # Check keywords
            if query.keywords and not descriptor.matches_keywords(query.keywords):
                continue

            # Check depth limit
            if context and not context.can_spawn_child():
                continue

            # Check cost hint
            if query.max_cost:
                cost_order = ["low", "medium", "high", "variable"]
                if cost_order.index(descriptor.cost_hint.value) > cost_order.index(query.max_cost):
                    continue

            # Check latency hint
            if query.max_latency:
                latency_order = ["interactive", "batch", "slow"]
                if latency_order.index(descriptor.latency_hint.value) > latency_order.index(query.max_latency):
                    continue

            matches.append(provider)

        return matches

    async def invoke(
        self,
        subagent_id: str,
        request: SubagentInvocationRequest,
        context: SubagentContext | None = None,
    ) -> SubagentInvocationResult:
        """Invoke a subagent and return the result.

        Args:
            subagent_id: ID of the subagent to invoke.
            request: The invocation request.
            context: Optional execution context.

        Returns:
            The invocation result.
        """
        provider = self._providers.get(subagent_id)
        if not provider:
            return SubagentInvocationResult.failure_result(
                request_id=request.request_id,
                subagent_id=subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_NOT_FOUND.value,
                error_message=f"Subagent '{subagent_id}' not found",
            )

        # Check policy
        policy = self._policies.get(subagent_id, SubagentRoutingPolicy())
        if context and not policy.can_be_invoked_by("orchestrator", context.depth):
            return SubagentInvocationResult.failure_result(
                request_id=request.request_id,
                subagent_id=subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_POLICY_DENIED.value,
                error_message="Invocation denied by policy",
            )

        # Check health
        if not await provider.health():
            return SubagentInvocationResult.failure_result(
                request_id=request.request_id,
                subagent_id=subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_UNHEALTHY.value,
                error_message=f"Subagent '{subagent_id}' is unhealthy",
            )

        # Apply timeout
        timeout = request.timeout_s or self._default_timeout_s

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    provider.invoke(request, context),
                    timeout=timeout,
                )
                return result
            except asyncio.TimeoutError:
                return SubagentInvocationResult.failure_result(
                    request_id=request.request_id,
                    subagent_id=subagent_id,
                    error_code=SubagentErrorCode.SUBAGENT_TIMEOUT.value,
                    error_message=f"Subagent '{subagent_id}' timed out after {timeout}s",
                )
            except Exception as e:
                logger.exception("Subagent '%s' invocation failed", subagent_id)
                return SubagentInvocationResult.failure_result(
                    request_id=request.request_id,
                    subagent_id=subagent_id,
                    error_code=SubagentErrorCode.SUBAGENT_BACKEND_ERROR.value,
                    error_message=str(e),
                )

    async def invoke_stream(
        self,
        subagent_id: str,
        request: SubagentInvocationRequest,
        context: SubagentContext | None = None,
    ) -> AsyncGenerator[SubagentProgressEvent, None]:
        """Invoke a subagent and yield progress events.

        Args:
            subagent_id: ID of the subagent to invoke.
            request: The invocation request.
            context: Optional execution context.

        Yields:
            SubagentProgressEvent: Progress events.
        """
        provider = self._providers.get(subagent_id)
        if not provider:
            yield SubagentProgressEvent.error(
                request_id=request.request_id,
                subagent_id=subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_NOT_FOUND.value,
                error_message=f"Subagent '{subagent_id}' not found",
            )
            return

        # Check policy
        policy = self._policies.get(subagent_id, SubagentRoutingPolicy())
        if context and not policy.can_be_invoked_by("orchestrator", context.depth):
            yield SubagentProgressEvent.error(
                request_id=request.request_id,
                subagent_id=subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_POLICY_DENIED.value,
                error_message="Invocation denied by policy",
            )
            return

        # Check health
        if not await provider.health():
            yield SubagentProgressEvent.error(
                request_id=request.request_id,
                subagent_id=subagent_id,
                error_code=SubagentErrorCode.SUBAGENT_UNHEALTHY.value,
                error_message=f"Subagent '{subagent_id}' is unhealthy",
            )
            return

        async with self._semaphore:
            try:
                async for event in provider.invoke_stream(request, context):
                    yield event
            except Exception as e:
                logger.exception("Subagent '%s' streaming failed", subagent_id)
                yield SubagentProgressEvent.error(
                    request_id=request.request_id,
                    subagent_id=subagent_id,
                    error_code=SubagentErrorCode.SUBAGENT_BACKEND_ERROR.value,
                    error_message=str(e),
                )

    async def cancel(self, request_id: str, subagent_id: str) -> bool:
        """Cancel an in-progress request.

        Args:
            request_id: ID of the request to cancel.
            subagent_id: ID of the subagent.

        Returns:
            True if cancellation was successful.
        """
        provider = self._providers.get(subagent_id)
        if not provider:
            return False

        runtime = await provider.get_runtime()
        return await runtime.cancel(request_id)

    async def cleanup(self) -> None:
        """Clean up all provider resources."""
        for provider in self._providers.values():
            try:
                await provider.cleanup()
            except Exception as e:
                logger.warning(
                    "Failed to cleanup subagent '%s': %s",
                    provider.subagent_id,
                    e,
                )

    async def discover_and_register(
        self,
        config: dict[str, Any] | None = None,
    ) -> int:
        """Discover subagents and register them.

        Args:
            config: Optional config for fallback discovery.

        Returns:
            Number of subagents registered.
        """
        subagent_classes = SubagentLoader.discover_subagents()

        if not subagent_classes and config:
            subagent_classes = SubagentLoader.discover_from_config(config)

        for cls in subagent_classes:
            try:
                self.register_runtime_class(cls)
            except Exception as e:
                logger.warning("Failed to register subagent %s: %s", cls.__name__, e)

        return len(subagent_classes)
