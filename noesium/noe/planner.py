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

from .prompts import PLANNING_PROMPT, REVISE_PLAN_PROMPT
from .state import TaskPlan, TaskStep

logger = logging.getLogger(__name__)

_VALID_HINTS = {"tool", "subagent", "cli_subagent", "auto"}


class TaskPlanner:
    """Decomposes a goal into a flat TaskPlan via LLM structured output."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        *,
        planning_llm: BaseLLMClient | None = None,
        cli_subagent_names: list[str] | None = None,
    ) -> None:
        self._llm = planning_llm or llm_client
        self._cli_subagent_names = cli_subagent_names or []

    def _cli_info(self) -> str:
        if not self._cli_subagent_names:
            return ""
        names = ", ".join(self._cli_subagent_names)
        return f" (available: {names})"

    async def create_plan(self, goal: str, context: str = "") -> TaskPlan:
        prompt = PLANNING_PROMPT.format(
            goal=goal,
            context=context,
            cli_subagent_info=self._cli_info(),
        )
        try:
            raw = self._llm.completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
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
        prompt = REVISE_PLAN_PROMPT.format(
            goal=plan.goal,
            original_steps=original_steps,
            feedback=feedback,
            completed_results="\n".join(completed_results),
        )
        try:
            raw = self._llm.completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
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
