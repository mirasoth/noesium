"""Node decorator for kernel metadata annotation (RFC-1001 Section 7)."""

from __future__ import annotations

import functools
from typing import Any, Callable


def kernel_node(
    *,
    deterministic: bool = True,
    entropy_sources: list[str] | None = None,
) -> Callable:
    """Annotate a graph node function with kernel execution metadata.

    The metadata is attached as ``_kernel_meta`` on the wrapped function
    and inspected by :class:`KernelExecutor` at runtime.

    Args:
        deterministic: Whether the node is free of external side effects.
        entropy_sources: Named entropy sources (e.g. ``["llm", "network"]``).
    """

    def decorator(fn: Callable) -> Callable:
        meta: dict[str, Any] = {
            "deterministic": deterministic,
            "entropy_sources": entropy_sources or [],
        }

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        import asyncio

        wrapper = async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper
        wrapper._kernel_meta = meta  # type: ignore[attr-defined]
        return wrapper

    return decorator
