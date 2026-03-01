"""Ephemeral in-memory storage (RFC-1001 Section 9.1)."""

from __future__ import annotations

from typing import Any


class EphemeralMemory:
    """Dict-backed transient memory. Sync, no IO."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def delete(self, key: str) -> bool:
        return self._data.pop(key, _MISSING) is not _MISSING

    def clear(self) -> None:
        self._data.clear()

    def keys(self) -> list[str]:
        return list(self._data.keys())


_MISSING = object()
