"""WebSocket handlers using Socket.IO."""

from __future__ import annotations

import socketio

from noecoder.services.task_orchestrator import TaskOrchestrator

# Socket.IO server instance
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Dependencies
task_orchestrator: TaskOrchestrator | None = None


@sio.event
async def connect(sid: str, environ: dict) -> None:
    """Client connected."""
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid: str) -> None:
    """Client disconnected."""
    print(f"Client disconnected: {sid}")


@sio.event
async def task_start(sid: str, data: dict) -> None:
    """Start task execution."""
    if task_orchestrator is None:
        await sio.emit("error", {"message": "Server not initialized"}, room=sid)
        return

    task_id = data.get("task_id")
    if not task_id:
        await sio.emit("error", {"message": "task_id required"}, room=sid)
        return

    try:
        await task_orchestrator.start_task(task_id, sio, sid)
    except Exception as e:
        await sio.emit("error", {"message": str(e)}, room=sid)


@sio.event
async def task_cancel(sid: str, data: dict) -> None:
    """Cancel running task."""
    if task_orchestrator is None:
        return

    task_id = data.get("task_id")
    if not task_id:
        return

    cancelled = await task_orchestrator.cancel_task(task_id)
    await sio.emit(
        "task.cancelled",
        {
            "task_id": task_id,
            "cancelled": cancelled,
        },
        room=sid,
    )
