"""Goal-based memory projection service (RFC-1005 §10, RFC-1002)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from noeagent.autonomous.goal_engine import Goal

    from noesium.core.memory.provider_manager import ProviderMemoryManager

logger = logging.getLogger(__name__)


class MemoryProjector:
    """Provides goal-based memory context projection.

    Implements the Projection Model from RFC-1002:
        Global Memory → Projection(goal) → Agent Context

    This class separates the projection logic from the CognitiveLoop,
    respecting the architectural diagram where Memory handles projection.

    Example:
        projector = MemoryProjector(memory_manager)
        context = await projector.project(goal)
        # context contains goal-related memories, history, and traces
    """

    def __init__(self, memory_manager: ProviderMemoryManager):
        """Initialize projector with memory manager.

        Args:
            memory_manager: ProviderMemoryManager instance
        """
        self.memory = memory_manager
        logger.debug("MemoryProjector initialized")

    async def project(self, goal: Goal) -> dict[str, Any]:
        """Project memory context for a specific goal.

        Retrieves relevant context from memory for reasoning:
        - Related memories via semantic search
        - Goal execution history
        - Previous execution traces

        Args:
            goal: Goal to project context for

        Returns:
            Memory context dictionary with:
            - goal_id, goal_description, goal_priority, goal_status
            - related_memories: top-k relevant memories
            - goal_history: previous executions of this goal
            - previous_execution: last execution trace
        """
        try:
            persistent = self.memory.get_provider("persistent")

            keywords = self._extract_keywords(goal.description)

            related = await self._search_related_memories(persistent, keywords, limit=10)

            goal_history = await persistent.read(f"goal:{goal.id}")
            execution_trace = await persistent.read(f"execution:{goal.id}")

            context = {
                "goal_id": goal.id,
                "goal_description": goal.description,
                "goal_priority": goal.priority,
                "goal_status": goal.status,
                "related_memories": related,
                "goal_history": goal_history.value if goal_history else None,
                "previous_execution": (execution_trace.value if execution_trace else None),
            }

            logger.debug(f"Projected memory context for goal {goal.id[:8]} with {len(related)} related memories")

            return context

        except Exception as e:
            logger.error(f"Failed to project memory: {e}", exc_info=True)
            return {
                "goal_id": goal.id,
                "goal_description": goal.description,
                "goal_priority": goal.priority,
                "goal_status": goal.status,
            }

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """Extract keywords from text for semantic search.

        Simple heuristic extraction. Can be enhanced with NLP.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to return

        Returns:
            List of keywords
        """
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
        }
        words = text.lower().split()
        keywords = [w.strip(".,!?;:") for w in words if len(w) > 3 and w.lower() not in stopwords]
        return keywords[:max_keywords]

    async def _search_related_memories(
        self,
        provider: Any,
        keywords: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for related memories using keywords.

        Args:
            provider: Memory provider with search capability
            keywords: Keywords to search for
            limit: Maximum results to return

        Returns:
            List of related memory entries with scores
        """
        try:
            query = " ".join(keywords)
            results = await provider.search(
                query=query,
                limit=limit,
                content_types=["fact", "execution_trace", "goal"],
            )

            return [
                {
                    "key": result.entry.key,
                    "value": result.entry.value,
                    "score": result.score,
                    "content_type": result.entry.content_type,
                }
                for result in results[:5]
            ]
        except Exception as e:
            logger.debug(f"Semantic search not available: {e}")
            return []
