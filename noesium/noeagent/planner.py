"""Task planner for goal decomposition (impl guide §5.2, §5.11).

Replaces the deprecated Goalith LLMDecomposer with a simpler flat-plan model.
Supports execution hints for intelligent tool-vs-subagent routing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from noesium.core.exceptions import PlanningError
from noesium.core.llm.base import BaseLLMClient

from .prompts import get_prompt_manager
from .state import TaskPlan, TaskStep

logger = logging.getLogger(__name__)

_VALID_HINTS = {"tool", "subagent", "external_subagent", "builtin_agent", "auto"}


class TaskPlanner:
    """Decomposes a goal into a flat TaskPlan via LLM structured output."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        *,
        planning_llm: BaseLLMClient | None = None,
        external_subagent_names: list[str] | None = None,
        builtin_subagent_names: list[str] | None = None,
        builtin_subagent_configs: list[Any] | None = None,
    ) -> None:
        self._llm = planning_llm or llm_client
        self._external_subagent_names = external_subagent_names or []
        self._builtin_subagent_names = builtin_subagent_names or []
        self._builtin_subagent_configs = builtin_subagent_configs or []

    def _external_info(self) -> str:
        if not self._external_subagent_names:
            return ""
        names = ", ".join(self._external_subagent_names)
        return f" (available: {names})"

    def _builtin_info(self) -> str:
        """Format detailed subagent capability information for the planning prompt.

        Excludes subagents that require_explicit_command=True (they can only be
        invoked via explicit /command, not auto-routed by LLM).
        """
        if not self._builtin_subagent_configs:
            # Fallback to simple names if no configs available
            if not self._builtin_subagent_names:
                return ""
            names = ", ".join(self._builtin_subagent_names)
            return f" (available: {names})"

        # Build rich capability descriptions (exclude requires_explicit_command=True)
        lines = []
        for cfg in self._builtin_subagent_configs:
            # Get attributes safely (handles both dict and object)
            if isinstance(cfg, dict):
                name = cfg.get("name", "unknown")
                desc = cfg.get("description", "")
                task_types = cfg.get("task_types", [])
                use_cases = cfg.get("use_cases", [])
                keywords = cfg.get("keywords", [])
                requires_explicit = cfg.get("requires_explicit_command", False)
            else:
                name = getattr(cfg, "name", "unknown")
                desc = getattr(cfg, "description", "")
                task_types = getattr(cfg, "task_types", [])
                use_cases = getattr(cfg, "use_cases", [])
                keywords = getattr(cfg, "keywords", [])
                requires_explicit = getattr(cfg, "requires_explicit_command", False)

            # Skip subagents that require explicit command (e.g., tacitus)
            if requires_explicit:
                continue

            lines.append(f"\n  **{name}**: {desc}")
            if task_types:
                lines.append(f"    - Task types: {', '.join(task_types)}")
            if use_cases:
                lines.append(f"    - Best for: {'; '.join(use_cases[:3])}")
            if keywords:
                lines.append(f"    - Keywords: {', '.join(keywords[:5])}")

        return "\n".join(lines)

    async def create_plan(self, goal: str, context: str = "") -> TaskPlan:
        pm = get_prompt_manager()
        prompt = pm.render(
            "planning",
            goal=goal,
            context=context,
            external_subagent_info=self._external_info(),
            builtin_subagent_info=self._builtin_info(),
        )
        try:
            # Run synchronous LLM call in thread pool to avoid blocking
            import asyncio

            raw = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._llm.completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                ),
            )
            steps = self._parse_steps(raw)
            return TaskPlan(goal=goal, steps=steps)
        except Exception as exc:
            logger.warning("Planning failed, falling back to single-step plan: %s", exc)
            return TaskPlan(
                goal=goal,
                steps=[TaskStep(description=goal)],
            )

    async def revise_plan(
        self,
        plan: TaskPlan,
        feedback: str,
        completed_results: list[str],
    ) -> TaskPlan:
        original_steps = "\n".join(f"  {i + 1}. [{s.status}] {s.description}" for i, s in enumerate(plan.steps))
        pm = get_prompt_manager()
        prompt = pm.render(
            "revise_plan",
            goal=plan.goal,
            original_steps=original_steps,
            feedback=feedback,
            completed_results="\n".join(completed_results),
        )
        try:
            # Run synchronous LLM call in thread pool to avoid blocking
            import asyncio

            raw = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._llm.completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                ),
            )
            steps = self._parse_steps(raw)
            return TaskPlan(goal=plan.goal, steps=steps)
        except Exception as exc:
            raise PlanningError(f"Plan revision failed: {exc}") from exc

    def _parse_steps(self, raw: Any) -> list[TaskStep]:
        text = raw if isinstance(raw, str) else str(raw)
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            data = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            lines = [l.strip().lstrip("0123456789.-) ") for l in text.splitlines() if l.strip()]
            return [TaskStep(description=line) for line in lines if line]
        steps_raw = data.get("steps", [])
        result: list[TaskStep] = []
        for s in steps_raw:
            if isinstance(s, dict):
                desc = s.get("description", str(s))
                hint = s.get("execution_hint", "auto")
                if hint not in _VALID_HINTS:
                    hint = "auto"
                result.append(TaskStep(description=desc, execution_hint=hint))
            else:
                result.append(TaskStep(description=str(s)))
        return result
