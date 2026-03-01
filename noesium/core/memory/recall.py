"""Recall result merging and ranking helpers (RFC-2002 §8)."""

from __future__ import annotations

from .provider import MemoryTier, RecallResult

_TIER_RANK = {
    MemoryTier.WORKING: 3,
    MemoryTier.PERSISTENT: 2,
    MemoryTier.INDEXED: 1,
}


def merge_results(results: list[RecallResult], limit: int) -> list[RecallResult]:
    """Deduplicate by key, prefer highest score, then sort by tier rank and score."""
    seen: dict[str, RecallResult] = {}
    for r in results:
        existing = seen.get(r.entry.key)
        if existing is None or r.score > existing.score:
            seen[r.entry.key] = r
    merged = sorted(
        seen.values(),
        key=lambda r: (-_TIER_RANK.get(r.tier, 0), -r.score),
    )
    return merged[:limit]
