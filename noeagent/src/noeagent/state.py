"""State models for Noe graphs (impl guide §3.2, §4.2-4.3)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from uuid_extensions import uuid7str

try:
    from langchain_core.messages import BaseMessage
    from langgraph.graph import add_messages

    LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseMessage = Any  # type: ignore[assignment,misc]
    LANGCHAIN_AVAILABLE = False

    def add_messages(left: list, right: list) -> list:  # type: ignore[misc]
        return left + right


from typing import TypedDict


class TaskStep(BaseModel):
    step_id: str = Field(default_factory=lambda: uuid7str())
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None
    execution_hint: Literal["tool", "subagent", "external_subagent", "builtin_agent", "auto"] = "auto"

    def to_todo_line(self, index: int) -> str:
        marker = "x" if self.status == "completed" else " "
        return f"- [{marker}] {index}. {self.description}"


class TaskPlan(BaseModel):
    goal: str
    steps: list[TaskStep] = Field(default_factory=list)
    current_step_index: int = 0
    is_complete: bool = False

    @property
    def current_step(self) -> TaskStep | None:
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance(self) -> None:
        """Mark current step completed and move to next."""
        if self.current_step:
            self.current_step.status = "completed"
        self.current_step_index += 1
        if self.current_step_index >= len(self.steps):
            self.is_complete = True

    def to_todo_markdown(self) -> str:
        lines = [f"# Todo for: {self.goal}", ""]
        for idx, step in enumerate(self.steps, start=1):
            lines.append(step.to_todo_line(idx))
        return "\n".join(lines)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: TaskPlan | None
    iteration: int
    tool_results: list[dict[str, Any]]
    reflection: str
    final_answer: str
    context_summary: str  # RFC-1009: injected from CognitiveContext.export()


class AskState(TypedDict):
    messages: Annotated[list, add_messages]
    memory_context: list[dict[str, Any]]
    final_answer: str
    context_summary: str  # RFC-1010: injected from CognitiveContext.export()
