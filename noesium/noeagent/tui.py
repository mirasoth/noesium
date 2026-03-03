"""Rich-based terminal UI for NoeAgent (impl guide §5.6).

Provides a Claude Code-style compact progress display with:
  * Live-updating plan checklist
  * One-liner tool activity indicators (no verbose output)
  * Multi-subagent bracketed progress tracks
  * Dynamic "thinking..." progress with context-aware messages
  * Partial results and final answer as markdown
  * Session-level JSONL logging for full detail
  * Slash commands for mode switching, plan display, memory stats
  * Multiline input (backslash continuation)
  * Command history with up/down arrow navigation
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

# Thinking messages for different phases
THINKING_MESSAGES = {
    "planning": [
        "Planning approach...",
        "Breaking down the task...",
        "Creating execution plan...",
        "Analyzing requirements...",
    ],
    "executing": [
        "Working on task...",
        "Processing...",
        "Executing step...",
        "Making progress...",
    ],
    "reflecting": [
        "Reflecting on progress...",
        "Evaluating results...",
        "Checking quality...",
        "Reviewing output...",
    ],
    "finalizing": [
        "Preparing answer...",
        "Synthesizing results...",
        "Generating response...",
        "Finalizing output...",
    ],
    "tool_use": [
        "Using tools...",
        "Calling tool...",
        "Fetching data...",
        "Processing request...",
    ],
    "default": [
        "Thinking...",
    ],
}

if TYPE_CHECKING:
    from .agent import NoeAgent
    from .state import TaskPlan

from .config import NoeConfig, NoeMode
from .progress import ProgressEvent, ProgressEventType
from .session_log import SessionLogger

# ---------------------------------------------------------------------------
# Dynamic thinking text generator
# ---------------------------------------------------------------------------


class DynamicThinkingText:
    """Generates dynamic thinking text that changes over time."""

    def __init__(self) -> None:
        self._phase = "default"
        self._context = ""
        self._message_index = 0
        self._last_update = time.time()
        self._update_interval = 1.5  # Change message every 1.5 seconds

    def set_phase(self, phase: str, context: str = "") -> None:
        """Set the current thinking phase."""
        if phase != self._phase:
            self._phase = phase
            self._message_index = 0
            self._last_update = time.time()
        if context:
            self._context = context

    def get_text(self) -> str:
        """Get the current thinking text, updating periodically."""
        now = time.time()
        if now - self._last_update >= self._update_interval:
            messages = THINKING_MESSAGES.get(self._phase, THINKING_MESSAGES["default"])
            self._message_index = (self._message_index + 1) % len(messages)
            self._last_update = now

        messages = THINKING_MESSAGES.get(self._phase, THINKING_MESSAGES["default"])
        base_text = messages[self._message_index]

        if self._context:
            return f"{base_text} {self._context}"
        return base_text


# ---------------------------------------------------------------------------
# Plan rendering
# ---------------------------------------------------------------------------

_STATUS_MARKERS = {
    "pending": ("[ ]", "dim"),
    "in_progress": ("[>]", "bold yellow"),
    "completed": ("[✓]", "bold green"),
    "failed": ("[✗]", "bold red"),
}


def render_plan_table(plan: "TaskPlan") -> Table:
    """Build a Rich Table from a TaskPlan with Claude-style progress indicators."""
    table = Table(
        title=f"📋 Plan: {plan.goal}",
        title_style="bold cyan",
        show_lines=False,
        expand=False,
        min_width=50,
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Status", width=5)
    table.add_column("Step", ratio=1)

    for idx, step in enumerate(plan.steps, start=1):
        marker, style = _STATUS_MARKERS.get(step.status, ("[ ]", "dim"))
        # Add visual emphasis for in-progress steps
        if step.status == "in_progress":
            step_text = Text(step.description, style="yellow")
        elif step.status == "completed":
            step_text = Text(step.description, style="green")
        else:
            step_text = Text(step.description, style="dim")
        table.add_row(str(idx), Text(marker, style=style), step_text)
    return table


def render_compact_progress(plan: "TaskPlan | None", current_step: str = "") -> Text:
    """Render a compact one-line progress indicator like Claude's.

    Shows: "✓ Step 1/3 · In progress: Step 2"
    """
    if not plan:
        return Text("")

    completed = sum(1 for s in plan.steps if s.status == "completed")
    total = len(plan.steps)

    parts = []
    # Show completed count
    if completed > 0:
        parts.append((f"✓ {completed}/{total}", "green"))
    else:
        parts.append((f"○ {completed}/{total}", "dim"))

    # Show current step if any
    if current_step:
        parts.append((" · ", "dim"))
        parts.append((current_step[:60], "yellow"))

    return Text.assemble(*parts)


# ---------------------------------------------------------------------------
# Compact activity rendering
# ---------------------------------------------------------------------------


def _activity_line(event: ProgressEvent, thinking_gen: DynamicThinkingText | None = None) -> Text | None:
    """Produce a compact one-liner for an activity event, or None to skip."""
    etype = event.type

    if etype == ProgressEventType.TOOL_START:
        label = event.summary or f"Using {event.tool_name or 'tool'}"
        if thinking_gen:
            thinking_gen.set_phase("tool_use", f"({event.tool_name or 'tool'})")
        return Text.assemble(("  . ", "dim"), (label, "blue"))

    if etype == ProgressEventType.TOOL_END:
        label = event.tool_name or "tool"
        brief = (event.tool_result or "")[:100].replace("\n", " ")
        parts: list[tuple[str, str] | str] = [("  > ", "dim green"), (f"{label}", "green")]
        if brief:
            parts.append(("  ", ""))
            parts.append((brief[:80], "dim"))
        return Text.assemble(*parts)

    if etype == ProgressEventType.SUBAGENT_START:
        tag = event.subagent_id or "subagent"
        msg = event.summary or "spawned"
        if thinking_gen:
            thinking_gen.set_phase("executing", f"[{tag}]")
        if msg.startswith(f"[{tag}]"):
            return Text.assemble(("  ", ""), (f"[{tag}] ", "bold magenta"), (msg[len(f"[{tag}]") :].strip(), ""))
        return Text.assemble(("  ", ""), (f"[{tag}] ", "bold magenta"), (msg, ""))

    if etype == ProgressEventType.SUBAGENT_PROGRESS:
        tag = event.subagent_id or "subagent"
        return Text.assemble(("  ", ""), (f"[{tag}] ", "magenta"), (event.summary or "", "dim"))

    if etype == ProgressEventType.SUBAGENT_END:
        tag = event.subagent_id or "subagent"
        return Text.assemble(("  ", ""), (f"[{tag}] ", "green"), (event.summary or "done", "green"))

    if etype == ProgressEventType.THINKING:
        return Text.assemble(("  . ", "dim"), (event.summary or "Thinking...", "dim italic"))

    if etype == ProgressEventType.ERROR:
        return Text.assemble(("  ! ", "bold red"), (event.error or "unknown error", "red"))

    return None


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

SLASH_COMMANDS = {
    "/exit": "Exit the TUI",
    "/quit": "Exit the TUI",
    "/mode": "Switch mode: /mode ask | /mode agent",
    "/plan": "Show current task plan",
    "/memory": "Show memory stats",
    "/clear": "Clear the screen",
    "/help": "Show available commands",
    "/session": "Show current session log path",
}


def handle_slash_command(
    cmd: str,
    agent: "NoeAgent",
    console: Console,
    *,
    current_plan: "TaskPlan | None" = None,
    session_logger: SessionLogger | None = None,
) -> bool:
    """Handle a slash command. Returns True if the TUI should exit."""
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command in ("/exit", "/quit"):
        console.print("[dim]Goodbye.[/dim]")
        return True

    if command == "/help":
        table = Table(title="Slash Commands", show_lines=False)
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        for k, v in SLASH_COMMANDS.items():
            table.add_row(k, v)
        console.print(table)
        return False

    if command == "/mode":
        if arg in ("ask", "agent"):
            new_mode = NoeMode.ASK if arg == "ask" else NoeMode.AGENT
            agent.config = agent.config.model_copy(update={"mode": new_mode})
            console.print(f"[bold green]Switched to {arg} mode[/bold green]")
        else:
            console.print("[yellow]Usage: /mode ask | /mode agent[/yellow]")
        return False

    if command == "/plan":
        if current_plan:
            console.print(render_plan_table(current_plan))
        else:
            console.print("[dim]No active plan.[/dim]")
        return False

    if command == "/memory":
        if agent._memory_manager:
            loop = asyncio.get_event_loop()
            try:
                stats = loop.run_until_complete(agent._memory_manager.stats())
                console.print(
                    Panel(json.dumps(stats, indent=2, default=str), title="Memory Stats", border_style="cyan")
                )
            except Exception as exc:
                console.print(f"[red]Memory stats error: {exc}[/red]")
        else:
            console.print("[dim]No memory manager configured.[/dim]")
        return False

    if command == "/session":
        if session_logger:
            console.print(f"[dim]Session log: {session_logger.log_path}[/dim]")
        else:
            console.print("[dim]No session logger active.[/dim]")
        return False

    if command == "/clear":
        console.clear()
        return False

    console.print(f"[yellow]Unknown command: {command}. Type /help for help.[/yellow]")
    return False


# ---------------------------------------------------------------------------
# Input helpers with history support
# ---------------------------------------------------------------------------


class InputHistory:
    """Manages command history for TUI input."""

    def __init__(self, history_file: str, max_size: int = 1000):
        self.history_file = Path(history_file)
        self.max_size = max_size
        self.history: list[str] = []
        self.cursor_index = -1
        # Ensure parent directory exists
        self._ensure_dir()
        self._load_history()

    def _ensure_dir(self) -> None:
        """Ensure the history file directory exists."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load_history(self) -> None:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def _save_history(self) -> None:
        """Save history to file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w") as f:
                json.dump(self.history[-self.max_size :], f, indent=2)
        except Exception:
            pass

    def add(self, line: str) -> None:
        """Add a line to history."""
        if line.strip() and (not self.history or self.history[-1] != line):
            self.history.append(line)
            if len(self.history) > self.max_size:
                self.history = self.history[-self.max_size :]
            self._save_history()
        self.cursor_index = -1

    def up(self, current_input: str) -> str | None:
        """Move up in history. Returns the history item or None."""
        if not self.history:
            return None
        if self.cursor_index < len(self.history) - 1:
            self.cursor_index += 1
            return self.history[-(self.cursor_index + 1)]
        return None

    def down(self, current_input: str) -> str | None:
        """Move down in history. Returns the history item or None."""
        if self.cursor_index > 0:
            self.cursor_index -= 1
            return self.history[-(self.cursor_index + 1)]
        elif self.cursor_index == 0:
            self.cursor_index = -1
            return ""
        return None

    def reset_cursor(self) -> None:
        """Reset cursor position."""
        self.cursor_index = -1


def read_user_input(console: Console, mode: str = "agent", history: InputHistory | None = None) -> str | None:
    """Read user input with backslash continuation for multiline and history support.

    Returns None on EOF/interrupt (signals exit).
    """
    lines: list[str] = []
    # Plain text prompt for prompt_toolkit (Rich markup not supported)
    prompt_str = f"noe|{mode}> "
    continuation_str = "...  "
    # Rich-formatted prompt for fallback
    rich_prompt_str = f"[bold cyan]noe|{mode}>[/bold cyan] "
    rich_continuation_str = "[dim]...[/dim]  "

    # Try using prompt_toolkit for better history support
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.styles import Style

        # Define a simple style for prompt_toolkit
        style = Style.from_dict(
            {
                "prompt": "bold cyan",
            }
        )

        # Use InMemoryHistory populated from our InputHistory
        # (FileHistory uses plain text format, incompatible with our JSON format)
        ptk_history = InMemoryHistory()
        if history:
            # Pre-populate with existing history (in reverse order so most recent is first)
            for entry in reversed(history.history):
                ptk_history.append_string(entry)

        session = PromptSession(history=ptk_history)

        try:
            # Use a formatted prompt with prompt_toolkit style
            first = session.prompt([("class:prompt", prompt_str)], style=style)
        except (EOFError, KeyboardInterrupt):
            return None

        if first.endswith("\\"):
            lines.append(first[:-1])
            while True:
                try:
                    cont = session.prompt(continuation_str, style=style)
                except (EOFError, KeyboardInterrupt):
                    break
                if cont.endswith("\\"):
                    lines.append(cont[:-1])
                else:
                    lines.append(cont)
                    break
            result = "\n".join(lines)
        else:
            result = first

        # Add to our history for persistence (prompt_toolkit already added to InMemoryHistory)
        if history and result.strip():
            history.add(result)

        return result

    except ImportError:
        # Fallback to Rich Prompt without history navigation
        try:
            first = Prompt.ask(rich_prompt_str, console=console, show_default=False)
        except (EOFError, KeyboardInterrupt):
            return None

        if first.endswith("\\"):
            lines.append(first[:-1])
            while True:
                try:
                    cont = Prompt.ask(rich_continuation_str, console=console, show_default=False)
                except (EOFError, KeyboardInterrupt):
                    break
                if cont.endswith("\\"):
                    lines.append(cont[:-1])
                else:
                    lines.append(cont)
                    break
            result = "\n".join(lines)
        else:
            result = first

        # Add to history if provided
        if history and result.strip():
            history.add(result)

        return result


# ---------------------------------------------------------------------------
# Async event-driven display loop
# ---------------------------------------------------------------------------


async def _process_query(
    agent: "NoeAgent",
    user_input: str,
    console: Console,
    session_logger: SessionLogger | None = None,
) -> "TaskPlan | None":
    """Process a single user query with compact Claude Code-style output.

    Args:
        agent: The NoeAgent instance
        user_input: User's query
        console: Rich console for output
        session_logger: Optional session logger
    """
    from .state import TaskPlan

    current_plan: TaskPlan | None = None
    activity_lines: list[Text] = []
    partial_results: list[str] = []
    final_answer: str = ""
    current_step_summary: str = ""
    step_details: list[Text] = []  # Step progress details

    # Dynamic thinking text generator
    thinking_gen = DynamicThinkingText()
    thinking_gen.set_phase("planning")

    def _get_spinner() -> Spinner:
        """Get a spinner with dynamic thinking text."""
        return Spinner("dots", text=thinking_gen.get_text(), style="cyan")

    def _build_display() -> Group:
        """Assemble the live-updating renderable group."""
        parts: list[object] = []
        # Show compact progress line at top
        if current_plan:
            compact = render_compact_progress(current_plan, current_step_summary)
            if compact:
                parts.append(compact)
                parts.append(Text(""))
        # Show full plan table (enabled by default)
        if current_plan:
            parts.append(render_plan_table(current_plan))
            parts.append(Text(""))
        # Show step details (enabled by default)
        if step_details:
            for detail in step_details[-5:]:
                parts.append(detail)
            parts.append(Text(""))
        for line in activity_lines[-15:]:
            parts.append(line)
        parts.append(Text(""))
        parts.append(_get_spinner())
        return Group(*parts)

    from rich.live import Live

    with Live(_build_display(), console=console, refresh_per_second=8, transient=True):
        async for event in agent.astream_progress(user_input):
            etype = event.type

            if etype == ProgressEventType.PLAN_CREATED:
                if event.plan_snapshot:
                    current_plan = TaskPlan(**event.plan_snapshot)
                thinking_gen.set_phase("executing")
                if current_plan:
                    step_details.append(Text(f"📋 Plan created with {len(current_plan.steps)} steps", style="dim"))

            elif etype == ProgressEventType.PLAN_REVISED:
                if event.plan_snapshot:
                    current_plan = TaskPlan(**event.plan_snapshot)
                thinking_gen.set_phase("executing")
                step_details.append(Text("📝 Plan revised", style="dim"))

            elif etype == ProgressEventType.STEP_START:
                current_step_summary = event.summary or ""
                if current_plan and event.step_index is not None:
                    idx = event.step_index
                    if idx < len(current_plan.steps):
                        current_plan.steps[idx].status = "in_progress"
                        thinking_gen.set_phase("executing", f"step {idx + 1}")
                        step_desc = current_plan.steps[idx].description[:60]
                        step_details.append(
                            Text.assemble((f"  [>] ", "bold yellow"), (f"Step {idx + 1}: ", "bold"), (step_desc, ""))
                        )

            elif etype == ProgressEventType.STEP_COMPLETE:
                if current_plan and event.step_index is not None:
                    idx = event.step_index
                    if idx < len(current_plan.steps):
                        current_plan.steps[idx].status = "completed"
                        step_desc = current_plan.steps[idx].description[:60]
                        step_details.append(
                            Text.assemble((f"  [✓] ", "bold green"), (f"Step {idx + 1}: ", "bold"), (step_desc, "dim"))
                        )

            elif etype in (
                ProgressEventType.TOOL_START,
                ProgressEventType.TOOL_END,
                ProgressEventType.SUBAGENT_START,
                ProgressEventType.SUBAGENT_PROGRESS,
                ProgressEventType.SUBAGENT_END,
                ProgressEventType.ERROR,
            ):
                line = _activity_line(event, thinking_gen)
                if line:
                    activity_lines.append(line)
                # Also add tool/subagent details to step_details
                if etype == ProgressEventType.TOOL_START and event.tool_name:
                    step_details.append(Text.assemble(("    → ", "dim"), (f"Using tool: {event.tool_name}", "blue")))

            elif etype == ProgressEventType.THINKING:
                # Update thinking phase based on the thinking event
                if event.summary:
                    # Map thinking summary to phase
                    summary_lower = event.summary.lower()
                    if "plan" in summary_lower:
                        thinking_gen.set_phase("planning")
                    elif "reflect" in summary_lower or "evaluat" in summary_lower:
                        thinking_gen.set_phase("reflecting")
                    elif "final" in summary_lower or "synthes" in summary_lower:
                        thinking_gen.set_phase("finalizing")
                    elif "tool" in summary_lower or "deciding" in summary_lower:
                        thinking_gen.set_phase("tool_use")
                    else:
                        thinking_gen.set_phase("executing")
                line = _activity_line(event, thinking_gen)
                if line:
                    activity_lines.append(line)

            elif etype == ProgressEventType.PARTIAL_RESULT:
                if event.text:
                    partial_results.append(event.text)

            elif etype == ProgressEventType.TEXT_CHUNK:
                pass

            elif etype == ProgressEventType.REFLECTION:
                activity_lines.append(Text.assemble(("  . ", "dim"), ("Reflected on progress", "dim italic")))
                thinking_gen.set_phase("reflecting")
                step_details.append(Text("  💭 Reflection completed", style="dim italic"))

            elif etype == ProgressEventType.FINAL_ANSWER:
                final_answer = event.text or ""
                thinking_gen.set_phase("finalizing")
                # Mark all remaining steps as completed when final answer is received
                if current_plan:
                    for step in current_plan.steps:
                        if step.status in ("in_progress", "pending"):
                            step.status = "completed"
                    current_plan.is_complete = True
                step_details.append(Text("  ✓ Final answer generated", style="bold green"))

            elif etype == ProgressEventType.SESSION_END:
                # Ensure all steps are marked completed at session end
                if current_plan:
                    for step in current_plan.steps:
                        if step.status in ("in_progress", "pending"):
                            step.status = "completed"
                    current_plan.is_complete = True

    # --- Post-processing: render static output ---

    if current_plan:
        console.print(render_plan_table(current_plan))

    for pr in partial_results:
        console.print()
        console.print(Rule(style="dim"))
        console.print(Markdown(pr))

    if final_answer:
        console.print()
        if partial_results or current_plan:
            console.print(Rule(style="dim"))
        console.print(Markdown(final_answer))
        console.print()

    return current_plan


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------


def run_agent_tui(agent: "NoeAgent") -> None:
    """Launch the interactive Rich TUI for NoeAgent.

    Ctrl+C behavior:
    - First press during task execution: Cancel current task, return to prompt
    - Second press at prompt (within 2 seconds): Exit the TUI
    """
    console = Console()
    current_plan: "TaskPlan | None" = None
    ctrl_c_count = 0  # Track consecutive ctrl+c presses
    last_ctrl_c_time = 0.0  # Timestamp of last ctrl+c
    ctrl_c_timeout = 2.0  # Seconds to reset the counter

    session_logger: SessionLogger | None = None
    if agent.config.enable_session_logging:
        session_logger = SessionLogger(log_dir=agent.config.session_log_dir)
        if session_logger not in agent.config.progress_callbacks:
            agent.config.progress_callbacks.append(session_logger)

    # Initialize input history
    history = InputHistory(
        history_file=agent.config.tui_history_file,
        max_size=agent.config.tui_history_size,
    )

    console.print(
        Panel(
            "[bold]NoeAgent[/bold] -- Autonomous Research Assistant\n"
            f"Mode: [cyan]{agent.config.mode.value}[/cyan]  |  "
            "Type [bold cyan]/help[/bold cyan] for commands, "
            "[bold cyan]/exit[/bold cyan] to quit."
            + (f"\nSession log: [dim]{session_logger.log_path}[/dim]" if session_logger else ""),
            border_style="bright_blue",
        )
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            user_input = read_user_input(console, mode=agent.config.mode.value, history=history)
            if user_input is None:
                # Check for double ctrl+c
                now = time.time()
                if now - last_ctrl_c_time < ctrl_c_timeout:
                    ctrl_c_count += 1
                else:
                    ctrl_c_count = 1
                last_ctrl_c_time = now

                if ctrl_c_count >= 2:
                    console.print("\n[bold red]Exiting...[/bold red]")
                    break
                else:
                    console.print("\n[yellow]Press Ctrl+C again to exit, or enter a command to continue.[/yellow]")
                    continue

            # Reset counter on valid input
            ctrl_c_count = 0

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                should_exit = handle_slash_command(
                    user_input,
                    agent,
                    console,
                    current_plan=current_plan,
                    session_logger=session_logger,
                )
                if should_exit:
                    break
                continue

            console.print()

            try:
                # Create a task for the query so we can cancel it
                task = loop.create_task(_process_query(agent, user_input, console, session_logger=session_logger))
                current_plan = loop.run_until_complete(task)
            except KeyboardInterrupt:
                # Task was cancelled by ctrl+c
                console.print("\n[yellow]Task cancelled. Press Ctrl+C again to exit.[/yellow]")
                last_ctrl_c_time = time.time()
                ctrl_c_count = 1
            except asyncio.CancelledError:
                console.print("\n[yellow]Task cancelled. Press Ctrl+C again to exit.[/yellow]")
                last_ctrl_c_time = time.time()
                ctrl_c_count = 1
            except Exception as exc:
                console.print(Text(f"  ! {exc}", style="bold red"))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Unified entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for NoeAgent TUI."""
    import os

    from noesium.core.utils.logging import setup_logging

    # Try to load from global config file first, fall back to defaults
    try:
        config = NoeConfig.from_global_config()
        config = config.model_copy(update={"interface_mode": "tui"})
    except Exception:
        # Fall back to defaults if global config doesn't exist or is invalid
        config = NoeConfig(mode=NoeMode.AGENT, interface_mode="tui")

    # Load dotenv if enabled
    config.load_dotenv_if_enabled()

    # Set logging level based on verbose setting
    log_level = "INFO" if config.verbose else "WARNING"
    log_file = os.getenv("NOESIUM_TUI_LOG_FILE")
    setup_logging(
        level=log_level,
        log_file=log_file,
        log_file_level="DEBUG",
        enable_colors=False,
        third_party_level="ERROR",
    )

    from .agent import NoeAgent

    agent = NoeAgent(config)
    run_agent_tui(agent)


if __name__ == "__main__":
    main()
