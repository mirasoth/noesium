"""Task API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from voyager.models.task import Task, TaskCreate, TaskStatus
from voyager.services.state_manager import StateManager
from voyager.services.task_orchestrator import TaskOrchestrator

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Dependencies (injected via app state)
state_manager: StateManager | None = None
task_orchestrator: TaskOrchestrator | None = None


@router.get("", response_model=list[Task])
async def list_tasks(
    status: TaskStatus | None = Query(None),
    repository_id: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> list[Task]:
    """List tasks with optional filtering."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    return await state_manager.list_tasks(
        status=status,
        repository_id=repository_id,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=Task)
async def create_task(data: TaskCreate) -> Task:
    """Create a new task."""
    if task_orchestrator is None:
        raise HTTPException(500, "Server not initialized")
    return await task_orchestrator.create_task(
        title=data.title,
        description=data.description,
        repository_id=data.repository_id,
        branch=data.branch,
        subagents=data.subagents,
    )


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    """Get task details."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> dict[str, bool]:
    """Delete a task."""
    if state_manager is None or task_orchestrator is None:
        raise HTTPException(500, "Server not initialized")
    if task_orchestrator.is_task_running(task_id):
        raise HTTPException(400, "Cannot delete running task")

    deleted = await state_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(404, "Task not found")
    return {"deleted": True}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict[str, bool]:
    """Cancel running task."""
    if task_orchestrator is None:
        raise HTTPException(500, "Server not initialized")
    cancelled = await task_orchestrator.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(400, "Task is not running")
    return {"cancelled": True}


@router.get("/{task_id}/events")
async def get_task_events(
    task_id: str, limit: int = Query(100)
) -> dict[str, list[dict[str, Any]]]:
    """Get task event log."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    events = await state_manager.get_events(task_id, limit)
    return {"events": [e.model_dump() for e in events]}


@router.get("/{task_id}/changes")
async def get_task_changes(task_id: str) -> dict[str, list[dict[str, Any]]]:
    """Get code changes from task."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    return {"changes": [c.model_dump() for c in task.code_changes]}


@router.get("/{task_id}/artifacts")
async def get_task_artifacts(task_id: str) -> dict[str, list[dict[str, Any]]]:
    """Get artifacts from task."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")

    return {"artifacts": [a.model_dump() for a in task.artifacts]}
