"""Task Orchestrator - bridges WebSocket to NoeAgent execution."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import socketio
from noeagent.progress import ProgressEvent, ProgressEventType
from voyager.config import VoyagerConfig
from voyager.models.events import ProgressEventData
from voyager.models.task import Task, TaskStatus, TaskStep
from voyager.services.git_client import GitClient
from voyager.services.session_manager import SessionManager
from voyager.services.state_manager import StateManager


class TaskOrchestrator:
    """Orchestrates task lifecycle and NoeAgent integration."""

    def __init__(
        self,
        state_manager: StateManager,
        session_manager: SessionManager,
        git_client: GitClient,
        config: VoyagerConfig,
    ):
        self._state = state_manager
        self._sessions = session_manager
        self._git = git_client
        self._config = config

        # Track running tasks
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    async def create_task(
        self,
        title: str | None,
        description: str,
        repository_id: str | None = None,
        branch: str | None = None,
        subagents: list[str] | None = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            title=title or description[:100],
            description=description,
            repository_id=repository_id,
            branch=branch,
            subagents=subagents,
            status=TaskStatus.CREATED,
        )
        await self._state.save_task(task)
        return task

    async def start_task(
        self, task_id: str, sio: socketio.AsyncServer, sid: str
    ) -> None:
        """Start task execution with WebSocket streaming."""
        task = await self._state.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        # Update status
        task.status = TaskStatus.PLANNING
        task.updated_at = datetime.utcnow()
        await self._state.save_task(task)

        # Create cancel event
        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event

        # Start execution in background
        async def run() -> None:
            try:
                await self._execute_task(task, sio, sid, cancel_event)
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.updated_at = datetime.utcnow()
                await self._state.save_task(task)
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.updated_at = datetime.utcnow()
                await self._state.save_task(task)
                await self._emit_error(sio, sid, task_id, str(e))
            finally:
                self._cancel_events.pop(task_id, None)

        self._running_tasks[task_id] = asyncio.create_task(run())

    async def _execute_task(
        self,
        task: Task,
        sio: socketio.AsyncServer,
        sid: str,
        cancel_event: asyncio.Event,
    ) -> None:
        """Execute task with NoeAgent, streaming progress."""

        # Emit task started
        await sio.emit(
            "task.started",
            {
                "task_id": task.task_id,
                "status": "planning",
            },
            room=sid,
        )

        # Get NoeAgent instance
        agent = await self._sessions.get_agent(task.repository_id)

        # Build context
        context = await self._build_context(task)

        # Stream progress events. Pass subagent_names when client specified subagents.
        async for event in agent.astream_progress(
            task.description,
            context,
            subagent_names=task.subagents,
        ):
            # Check for cancellation
            if cancel_event.is_set():
                raise asyncio.CancelledError()

            # Store event
            progress_event = self._map_progress_event(event)
            await self._state.append_event(task.task_id, progress_event)

            # Update task state based on event
            await self._update_task_from_event(task, event)

            # Emit to WebSocket
            await sio.emit(
                "progress",
                {
                    "task_id": task.task_id,
                    "event": event.model_dump(),
                },
                room=sid,
            )

        # Mark completed
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        await self._state.save_task(task)

        # Emit completion
        await sio.emit(
            "task.completed",
            {
                "task_id": task.task_id,
                "final_answer": task.final_answer,
                "code_changes": [c.model_dump() for c in task.code_changes],
            },
            room=sid,
        )

    async def _build_context(self, task: Task) -> dict[str, Any]:
        """Build execution context for NoeAgent."""
        context: dict[str, Any] = {}

        if task.repository_id:
            repo = await self._state.get_repository(task.repository_id)
            if repo:
                context["repository"] = {
                    "name": repo.name,
                    "path": str(repo.local_path),
                    "branch": task.branch or repo.default_branch,
                }

                # Get recent changes
                try:
                    status = await self._git.get_status(Path(repo.local_path))
                    context["git_status"] = status
                except Exception:
                    pass

        return context

    async def _update_task_from_event(self, task: Task, event: ProgressEvent) -> None:
        """Update task state from NoeAgent progress event."""
        if event.type == ProgressEventType.PLAN_CREATED:
            task.status = TaskStatus.EXECUTING
            if event.plan_snapshot:
                # Extract steps from plan
                steps_data = event.plan_snapshot.get("steps", [])
                task.steps = [TaskStep(**s) for s in steps_data]

        elif event.type == ProgressEventType.STEP_START:
            if event.step_index is not None:
                task.current_step_index = event.step_index
                if event.step_index < len(task.steps):
                    task.steps[event.step_index].status = "in_progress"
                    task.steps[event.step_index].started_at = datetime.utcnow()

        elif event.type == ProgressEventType.STEP_COMPLETE:
            if event.step_index is not None and event.step_index < len(task.steps):
                task.steps[event.step_index].status = "completed"
                task.steps[event.step_index].completed_at = datetime.utcnow()
                if event.summary:
                    task.steps[event.step_index].result = event.summary

        elif event.type == ProgressEventType.REFLECTION:
            task.status = TaskStatus.REFLECTING
            if event.text:
                task.reasoning_trace.append(
                    {
                        "type": "reflection",
                        "text": event.text,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        elif event.type == ProgressEventType.FINAL_ANSWER:
            if event.text:
                task.final_answer = event.text

        elif event.type == ProgressEventType.ERROR:
            task.error_message = event.error or event.summary

        elif event.type == ProgressEventType.TOOL_END:
            if event.tool_name:
                task.tool_invocations.append(
                    {
                        "tool": event.tool_name,
                        "args": event.tool_args,
                        "result": (
                            event.tool_result[:500] if event.tool_result else None
                        ),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        task.updated_at = datetime.utcnow()
        await self._state.save_task(task)

    def _map_progress_event(self, event: ProgressEvent) -> ProgressEventData:
        """Map NoeAgent ProgressEvent to our event model."""
        return ProgressEventData(
            event_type=event.type.value,
            session_id=event.session_id,
            sequence=event.sequence,
            summary=event.summary,
            detail=event.detail,
            step_index=event.step_index,
            step_desc=event.step_desc,
            tool_name=event.tool_name,
            tool_args=event.tool_args,
            tool_result=event.tool_result[:1000] if event.tool_result else None,
            text=event.text,
            error=event.error,
        )

    async def _emit_error(
        self, sio: socketio.AsyncServer, sid: str, task_id: str, error: str
    ) -> None:
        """Emit error event."""
        await sio.emit(
            "task.error",
            {
                "task_id": task_id,
                "error": error,
            },
            room=sid,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel running task."""
        if task_id in self._cancel_events:
            self._cancel_events[task_id].set()
            return True
        return False

    def is_task_running(self, task_id: str) -> bool:
        """Check if task is currently running."""
        return task_id in self._running_tasks
