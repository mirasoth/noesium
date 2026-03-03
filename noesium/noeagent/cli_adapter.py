"""External CLI subagent adapter (impl guide §5.10).

Manages CLI subagent execution in two modes:
1. daemon: Long-lived persistent process with bidirectional JSON streaming
2. oneshot: Single execution per request, process exits after completion

Supports various CLI agents including Claude Code CLI with proper NDJSON parsing.
Implements the persistent daemon model from RFC-0005 §10.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
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


class CliExecutionResult(BaseModel):
    """Result from a CLI execution (oneshot or daemon mode)."""

    success: bool = True
    content: str = ""
    raw_output: str = ""
    error: str | None = None
    exit_code: int | None = None
    execution_time: float = 0.0  # seconds


class OutputParser:
    """Parser for different CLI output formats."""

    @staticmethod
    def parse(raw: bytes, output_format: str) -> str:
        """Parse raw output bytes according to the specified format.

        Args:
            raw: Raw output bytes from the CLI
            output_format: One of 'text', 'json', 'stream-json', 'ndjson'

        Returns:
            Parsed content string
        """
        text = raw.decode("utf-8", errors="replace")

        if output_format == "text":
            return text.strip()

        if output_format == "json":
            # Single JSON object
            try:
                data = json.loads(text)
                return OutputParser._extract_content(data)
            except json.JSONDecodeError:
                return text.strip()

        if output_format in ("stream-json", "ndjson"):
            return OutputParser._parse_ndjson(text)

        return text.strip()

    @staticmethod
    def _parse_ndjson(text: str) -> str:
        """Parse NDJSON (newline-delimited JSON) output.

        Handles various streaming formats including:
        - Claude CLI stream-json format
        - Standard NDJSON with 'content', 'result', 'text' fields
        - Event-based streaming with 'type' field
        """
        lines = text.strip().split("\n")
        content_parts: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                extracted = OutputParser._extract_streaming_content(event)
                if extracted:
                    content_parts.append(extracted)
            except json.JSONDecodeError:
                # Non-JSON line, include as-is if meaningful
                if line and not line.startswith("{"):
                    content_parts.append(line)

        return "".join(content_parts)

    @staticmethod
    def _extract_streaming_content(event: dict[str, Any]) -> str:
        """Extract content from a streaming event object.

        Handles multiple event formats:
        - Claude CLI: {"type": "content_block_delta", "delta": {"text": "..."}}
        - Generic: {"content": "..."}, {"result": "..."}, {"text": "..."}
        - Message events: {"type": "message", "content": "..."}
        """
        event_type = event.get("type", "")

        # Claude CLI streaming format
        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if "text" in delta:
                return delta["text"]
            return ""

        if event_type == "message_stop":
            return ""

        if event_type == "message_start":
            return ""

        # Message content
        if event_type == "message":
            return event.get("content", "")

        # Generic formats
        for key in ("content", "result", "text", "response"):
            if key in event and isinstance(event[key], str):
                return event[key]

        # Nested content in 'message' field
        if "message" in event:
            msg = event["message"]
            if isinstance(msg, str):
                return msg
            if isinstance(msg, dict):
                for key in ("content", "text"):
                    if key in msg and isinstance(msg[key], str):
                        return msg[key]

        return ""

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        """Extract content from a single JSON object."""
        for key in ("content", "result", "text", "response", "output"):
            if key in data and isinstance(data[key], str):
                return data[key]
        return json.dumps(data)


class ClaudeCliAdapter:
    """Specialized adapter for Claude Code CLI.

    Claude CLI supports two modes:
    1. Interactive mode: claude (starts REPL)
    2. Print mode: claude -p "query" (single query, exits)

    For automation, we use print mode with stream-json output:
        claude -p --output-format stream-json "query"

    Claude CLI streaming output format (NDJSON):
        {"type":"message_start","message":{"id":"...","content":[]}}
        {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}
        {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}
        {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}
        {"type":"content_block_stop","index":0}
        {"type":"message_stop"}
    """

    def __init__(self, config: CliSubagentConfig):
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate Claude CLI configuration."""
        if self.config.command != "claude":
            logger.warning(
                "ClaudeCliAdapter initialized with non-claude command: %s",
                self.config.command,
            )

    def build_command_args(self, task: str, **kwargs: Any) -> list[str]:
        """Build command arguments for Claude CLI execution.

        Args:
            task: The task/query to send to Claude
            **kwargs: Additional options:
                - allowed_tools: List of tools to allow
                - skip_permissions: Whether to skip permission prompts
                - max_turns: Maximum agentic turns
                - workdir: Working directory context

        Returns:
            List of command arguments
        """
        args = list(self.config.args)  # Start with configured args

        # Ensure print mode for oneshot execution
        if "-p" not in args and "--print" not in args:
            args.insert(0, "-p")

        # Add output format
        if "--output-format" not in args:
            args.extend(["--output-format", "stream-json"])

        # Claude CLI requires --verbose for stream-json output
        if "--verbose" not in args:
            args.append("--verbose")

        # Add permission handling
        if self.config.skip_permissions or kwargs.get("skip_permissions"):
            if "--dangerously-skip-permissions" not in args:
                args.append("--dangerously-skip-permissions")

        # Add allowed tools if specified
        allowed = kwargs.get("allowed_tools", self.config.allowed_tools)
        if allowed:
            tools_str = ",".join(allowed)
            args.extend(["--allowedTools", tools_str])

        # Add max turns if specified
        max_turns = kwargs.get("max_turns")
        if max_turns:
            args.extend(["--max-turns", str(max_turns)])

        # The task is passed via stdin, not as an argument
        return args

    async def execute(self, task: str, **kwargs: Any) -> CliExecutionResult:
        """Execute a task using Claude CLI in oneshot mode.

        Args:
            task: The task/query to send to Claude
            **kwargs: Additional execution options

        Returns:
            CliExecutionResult with parsed content
        """
        import time

        start_time = time.monotonic()

        args = self.build_command_args(task, **kwargs)
        env = dict(self.config.env) if self.config.env else None

        logger.info("Executing Claude CLI: %s %s", self.config.command, shlex.join(args))

        try:
            proc = await asyncio.create_subprocess_exec(
                self.config.command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # Send task via stdin
            proc.stdin.write(task.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return CliExecutionResult(
                    success=False,
                    error=f"Claude CLI timed out after {self.config.timeout}s",
                    execution_time=time.monotonic() - start_time,
                )

            execution_time = time.monotonic() - start_time

            # Check exit code
            if proc.returncode and proc.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace").strip()
                return CliExecutionResult(
                    success=False,
                    raw_output=stdout.decode("utf-8", errors="replace"),
                    error=f"Claude CLI exited with code {proc.returncode}: {error_msg}",
                    exit_code=proc.returncode,
                    execution_time=execution_time,
                )

            # Parse output
            raw_output = stdout.decode("utf-8", errors="replace")
            content = OutputParser.parse(stdout, "stream-json")

            return CliExecutionResult(
                success=True,
                content=content,
                raw_output=raw_output,
                exit_code=proc.returncode,
                execution_time=execution_time,
            )

        except FileNotFoundError:
            return CliExecutionResult(
                success=False,
                error=f"Claude CLI command not found: {self.config.command}",
                execution_time=time.monotonic() - start_time,
            )
        except Exception as exc:
            logger.exception("Claude CLI execution failed")
            return CliExecutionResult(
                success=False,
                error=f"Claude CLI execution error: {exc}",
                execution_time=time.monotonic() - start_time,
            )


class ExternalCliAdapter:
    """Manages CLI subagent execution.

    Supports two modes:
    1. daemon: Long-lived persistent process with bidirectional JSON streaming
    2. oneshot: Single execution per request, process exits after completion

    For oneshot mode, each invocation spawns a new process, captures output,
    and returns the result. This is ideal for CLI tools like Claude CLI.
    """

    def __init__(self) -> None:
        self._handles: dict[str, SubagentHandle] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._configs: dict[str, CliSubagentConfig] = {}
        self._lock = asyncio.Lock()

    def register_config(self, config: CliSubagentConfig) -> None:
        """Register a CLI subagent configuration.

        This allows the adapter to execute oneshot commands without
        requiring a persistent daemon.
        """
        self._configs[config.name] = config

    @property
    def active_names(self) -> list[str]:
        return [n for n, h in self._handles.items() if h.state not in ("TERMINATED",)]

    # ------------------------------------------------------------------
    # Oneshot Execution (recommended for most CLI agents)
    # ------------------------------------------------------------------

    async def execute_oneshot(
        self,
        name: str,
        task: str,
        **kwargs: Any,
    ) -> CliExecutionResult:
        """Execute a CLI subagent in oneshot mode.

        This spawns a new process for each execution, captures all output,
        and returns the result. The process exits after completion.

        Args:
            name: Name of the registered CLI subagent config
            task: Task/message to send to the CLI
            **kwargs: Additional execution options

        Returns:
            CliExecutionResult with execution details
        """
        config = self._configs.get(name)
        if config is None:
            return CliExecutionResult(
                success=False,
                error=f"No CLI subagent config registered for '{name}'",
            )

        # Use specialized adapter for Claude CLI
        if config.command == "claude" or "claude" in name.lower():
            adapter = ClaudeCliAdapter(config)
            return await adapter.execute(task, **kwargs)

        # Generic oneshot execution
        return await self._execute_generic_oneshot(config, task, **kwargs)

    async def _execute_generic_oneshot(
        self,
        config: CliSubagentConfig,
        task: str,
        **kwargs: Any,
    ) -> CliExecutionResult:
        """Execute a generic CLI command in oneshot mode."""
        import time

        start_time = time.monotonic()
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

            # Send task via stdin
            if config.input_format == "stream-json":
                payload = json.dumps({"message": task}) + "\n"
            else:
                payload = task + "\n"

            proc.stdin.write(payload.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=config.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return CliExecutionResult(
                    success=False,
                    error=f"CLI '{config.name}' timed out after {config.timeout}s",
                    execution_time=time.monotonic() - start_time,
                )

            execution_time = time.monotonic() - start_time
            raw_output = stdout.decode("utf-8", errors="replace")

            # Parse output
            content = OutputParser.parse(stdout, config.output_format)

            # Include stderr in error if present
            error_msg = None
            if proc.returncode and proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace").strip()
                error_msg = f"CLI exited with code {proc.returncode}"
                if stderr_text:
                    error_msg += f": {stderr_text}"

            return CliExecutionResult(
                success=proc.returncode == 0 or proc.returncode is None,
                content=content,
                raw_output=raw_output,
                error=error_msg,
                exit_code=proc.returncode,
                execution_time=execution_time,
            )

        except FileNotFoundError:
            return CliExecutionResult(
                success=False,
                error=f"CLI command not found: {config.command}",
                execution_time=time.monotonic() - start_time,
            )
        except Exception as exc:
            logger.exception("CLI execution failed")
            return CliExecutionResult(
                success=False,
                error=f"CLI execution error: {exc}",
                execution_time=time.monotonic() - start_time,
            )

    # ------------------------------------------------------------------
    # Daemon Mode (persistent process)
    # ------------------------------------------------------------------

    async def spawn(self, name: str, initial_message: str = "") -> str:
        """Start a CLI subagent daemon and optionally send an initial message.

        Note: Daemon mode is deprecated in favor of oneshot mode for most CLI agents.
        """
        async with self._lock:
            if name in self._handles and self._handles[name].state != "TERMINATED":
                if initial_message:
                    return await self._send_unlocked(name, initial_message)
                return f"CLI subagent '{name}' is already running."

            config = self._configs.get(name)
            if config is None:
                # Fallback to handle-based config lookup
                configs_by_name = {h.config.name: h.config for h in self._handles.values()}
                config = configs_by_name.get(name)

            if config is None:
                return f"No CliSubagentConfig registered for '{name}'."

            return await self._spawn_with_config(config, initial_message)

    async def spawn_from_config(self, config: CliSubagentConfig, initial_message: str = "") -> str:
        """Start a daemon from an explicit config.

        Also registers the config for later oneshot execution.
        """
        self._configs[config.name] = config

        # For oneshot mode, just register the config
        if config.mode == "oneshot":
            return f"CLI subagent '{config.name}' registered for oneshot execution."

        async with self._lock:
            return await self._spawn_with_config(config, initial_message)

    async def _spawn_with_config(self, config: CliSubagentConfig, initial_message: str) -> str:
        """Spawn a persistent daemon process."""
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
        """Send a message to a running CLI subagent daemon.

        For oneshot-mode subagents, this will execute in oneshot mode instead.
        """
        # Check if this is a oneshot config
        config = self._configs.get(name)
        if config and config.mode == "oneshot":
            result = await self.execute_oneshot(name, message)
            return result.content if result.success else f"Error: {result.error}"

        async with self._lock:
            return await self._send_unlocked(name, message)

    async def _send_unlocked(self, name: str, message: str) -> str:
        """Send message to daemon process (internal)."""
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

    # ------------------------------------------------------------------
    # Lifecycle Management
    # ------------------------------------------------------------------

    async def health_check(self, name: str) -> bool:
        """Check if a CLI subagent daemon is still alive."""
        proc = self._processes.get(name)
        if proc is None:
            # For oneshot configs, check if config exists
            return name in self._configs
        return proc.returncode is None

    async def restart(self, name: str) -> str:
        """Terminate and re-spawn a CLI subagent daemon."""
        handle = self._handles.get(name)
        if handle is None:
            config = self._configs.get(name)
            if config:
                return f"CLI subagent '{name}' is registered for oneshot mode."
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

    def get_config(self, name: str) -> CliSubagentConfig | None:
        """Get the registered config for a CLI subagent."""
        return self._configs.get(name)

    def get_status(self) -> dict[str, Any]:
        """Return status summary of all managed CLI subagents."""
        return {
            "daemon_processes": {
                name: {
                    "state": h.state,
                    "pid": h.pid,
                    "session_id": h.session_id,
                    "started_at": h.started_at.isoformat(),
                }
                for name, h in self._handles.items()
            },
            "registered_configs": list(self._configs.keys()),
        }
