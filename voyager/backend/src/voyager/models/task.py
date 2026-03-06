"""Task models for Voyager."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStep(BaseModel):
    """A single step in the task execution plan."""

    step_id: str = Field(default_factory=uuid7str)
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    result: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CodeChange(BaseModel):
    """A code change made during task execution."""

    file_path: str
    change_type: str  # created, modified, deleted
    diff: str
    lines_added: int = 0
    lines_removed: int = 0


class Artifact(BaseModel):
    """An artifact produced during task execution."""

    artifact_id: str = Field(default_factory=uuid7str)
    artifact_type: str  # code, document, image
    content: str | None = None
    file_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class Task(BaseModel):
    """A coding task to be executed by NoeAgent."""

    task_id: str = Field(default_factory=uuid7str)
    title: str
    description: str
    status: TaskStatus = TaskStatus.CREATED
    repository_id: str | None = None
    branch: str | None = None

    # Optional: run with specific subagent(s); same message sent to each in sequence
    subagents: list[str] | None = None

    # Execution state
    steps: list[TaskStep] = []
    current_step_index: int = 0

    # Results
    code_changes: list[CodeChange] = []
    artifacts: list[Artifact] = []
    final_answer: str | None = None

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    completed_at: datetime | None = None

    # Reasoning trace
    reasoning_trace: list[dict[str, Any]] = []
    tool_invocations: list[dict[str, Any]] = []

    # Error info
    error_message: str | None = None


class TaskCreate(BaseModel):
    """Request body for creating a task."""

    title: str | None = None  # Optional, derived from description
    description: str = Field(..., description="User message for the agent.")
    repository_id: str | None = None
    branch: str | None = None
    subagents: list[str] | None = Field(
        None,
        description="Optional list of subagent names (e.g. ['browser_use', 'tacitus']). Same message is run by each in sequence.",
    )


class TaskUpdate(BaseModel):
    """Request body for updating a task."""

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
