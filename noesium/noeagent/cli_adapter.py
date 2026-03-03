"""External CLI subagent adapter (impl guide §5.10).

Manages persistent CLI subagent daemons (e.g. Claude Code CLI) that run as
long-lived child processes communicating via stdin/stdout JSON streaming.
Implements the persistent daemon model from RFC-0005 §10.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import CliSubagentConfig

logger = logging.getLogger(__name__)


class SubagentHandle(BaseModel):
    """Opaque handle to a running subagent daemon."""

    name: str
    config: CliSubagentConfig
    session_id: str
    state: Literal["CREATED", "RUNNING", "BUSY", "IDLE", "TERMINATED"] = "CREATED"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pid: int | None = None


class ExternalCliAdapter:
    """Manages persistent CLI subagent daemons.

    Each daemon is a long-lived process started via ``asyncio.create_subprocess_exec``.
    Communication uses stdin/stdout line-delimited JSON.
    """

    def __init__(self) -> None:
        self._handles: dict[str, SubagentHandle] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._lock = asyncio.Lock()

    @property
    def active_names(self) -> list[str]:
        return [n for n, h in self._handles.items() if h.state not in ("TERMINATED",)]

    async def spawn(self, name: str, initial_message: str = "") -> str:
        """Start a CLI subagent daemon and optionally send an initial message."""
        async with self._lock:
            if name in self._handles and self._handles[name].state != "TERMINATED":
                if initial_message:
                    return await self._send_unlocked(name, initial_message)
                return f"CLI subagent '{name}' is already running."

            configs_by_name = {h.config.name: h.config for h in self._handles.values()}
            config = configs_by_name.get(name)
            if config is None:
                return f"No CliSubagentConfig registered for '{name}'."

            return await self._spawn_with_config(config, initial_message)

    async def spawn_from_config(self, config: CliSubagentConfig, initial_message: str = "") -> str:
        """Start a daemon from an explicit config."""
        async with self._lock:
            return await self._spawn_with_config(config, initial_message)

    async def _spawn_with_config(self, config: CliSubagentConfig, initial_message: str) -> str:
        name = config.name
        env = dict(config.env) if config.env else None
        try:
            proc = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError:
            return f"CLI subagent command not found: {config.command}"
        except OSError as exc:
            return f"Failed to spawn CLI subagent '{name}': {exc}"

        from uuid_extensions import uuid7str

        handle = SubagentHandle(
            name=name,
            config=config,
            session_id=uuid7str(),
            state="RUNNING",
            pid=proc.pid,
        )
        self._handles[name] = handle
        self._processes[name] = proc
        logger.info("Spawned CLI subagent '%s' (pid=%s)", name, proc.pid)

        if initial_message:
            return await self._send_unlocked(name, initial_message)
        return f"CLI subagent '{name}' spawned (pid={proc.pid})."

    async def interact(self, name: str, message: str) -> str:
        """Send a message to a running CLI subagent and return its response."""
        async with self._lock:
            return await self._send_unlocked(name, message)

    async def _send_unlocked(self, name: str, message: str) -> str:
        handle = self._handles.get(name)
        if handle is None or handle.state == "TERMINATED":
            return f"CLI subagent '{name}' is not running."

        proc = self._processes.get(name)
        if proc is None or proc.stdin is None or proc.stdout is None:
            return f"CLI subagent '{name}' has no active process."

        handle.state = "BUSY"
        try:
            payload = json.dumps({"message": message}) + "\n"
            proc.stdin.write(payload.encode())
            await proc.stdin.drain()

            response_lines: list[str] = []
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=handle.config.timeout,
                )
                if line:
                    response_lines.append(line.decode().strip())
            except asyncio.TimeoutError:
                handle.state = "IDLE"
                return f"CLI subagent '{name}' timed out after {handle.config.timeout}s."

            handle.state = "IDLE"

            if not response_lines:
                return f"CLI subagent '{name}' returned empty response."

            raw = response_lines[0]
            try:
                data = json.loads(raw)
                return data.get("result", data.get("response", data.get("text", raw)))
            except json.JSONDecodeError:
                return raw

        except Exception as exc:
            handle.state = "IDLE"
            logger.warning("CLI subagent '%s' communication error: %s", name, exc)
            return f"CLI subagent '{name}' error: {exc}"

    async def health_check(self, name: str) -> bool:
        """Check if a CLI subagent daemon is still alive."""
        proc = self._processes.get(name)
        if proc is None:
            return False
        return proc.returncode is None

    async def restart(self, name: str) -> str:
        """Terminate and re-spawn a CLI subagent."""
        handle = self._handles.get(name)
        if handle is None:
            return f"No handle found for '{name}'."
        await self._terminate_proc(name)
        return await self._spawn_with_config(handle.config, "")

    async def terminate(self, name: str) -> str:
        """Terminate a specific CLI subagent daemon."""
        async with self._lock:
            return await self._terminate_proc(name)

    async def _terminate_proc(self, name: str) -> str:
        handle = self._handles.get(name)
        proc = self._processes.get(name)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
        if handle:
            handle.state = "TERMINATED"
        self._processes.pop(name, None)
        logger.info("Terminated CLI subagent '%s'", name)
        return f"CLI subagent '{name}' terminated."

    async def terminate_all(self) -> None:
        """Terminate all running CLI subagent daemons."""
        for name in list(self._processes):
            await self._terminate_proc(name)

    def get_handle(self, name: str) -> SubagentHandle | None:
        return self._handles.get(name)

    def get_status(self) -> dict[str, Any]:
        """Return status summary of all managed daemons."""
        return {
            name: {
                "state": h.state,
                "pid": h.pid,
                "session_id": h.session_id,
                "started_at": h.started_at.isoformat(),
            }
            for name, h in self._handles.items()
        }
