"""Skill composition model (RFC-2004 §9)."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field, PrivateAttr
from uuid_extensions import uuid7str

from noesium.core.exceptions import SkillNotFoundError


class Skill(BaseModel):
    """A named composition of one or more AtomicTools."""

    skill_id: str = Field(default_factory=lambda: uuid7str())
    name: str
    description: str
    tool_names: list[str]
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)

    _executor_fn: Callable | None = PrivateAttr(default=None)

    def bind_executor(self, fn: Callable) -> Skill:
        self._executor_fn = fn
        return self

    async def execute(
        self,
        tool_registry: Any,
        tool_executor: Any,
        context: Any,
        **kwargs: Any,
    ) -> Any:
        if self._executor_fn:
            return await self._executor_fn(
                tool_registry=tool_registry,
                tool_executor=tool_executor,
                context=context,
                **kwargs,
            )
        raise NotImplementedError("Skill has no bound executor")


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise SkillNotFoundError(f"Skill '{name}' not registered")
        return self._skills[name]

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())
