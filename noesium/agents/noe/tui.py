"""Rich-based terminal UI for NoeAgent (impl guide §5.6).

Provides a Claude Code-style compact progress display with:
  * Live-updating plan checklist
  * One-liner tool activity indicators (no verbose output)
  * Multi-subagent bracketed progress tracks
  * Partial results and final answer as markdown
  * Session-level JSONL logging for full detail
  * Slash commands for mode switching, plan display, memory stats
  * Multiline input (backslash continuation)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from .agent import NoeAgent
    from .state import TaskPlan

from .config import NoeConfig, NoeMode
from .progress import ProgressEvent, ProgressEventType
from .session_log import SessionLogger

# ---------------------------------------------------------------------------
# Plan rendering
# ---------------------------------------------------------------------------

_STATUS_MARKERS = {
    "pending": ("[ ]", "dim"),
    "in_progress": ("[>]", "bold yellow"),
    "completed": ("[x]", "green"),
    "failed": ("[!]", "bold red"),
}


def render_plan_table(plan: "TaskPlan") -> Table:
    """Build a Rich Table from a TaskPlan."""
    table = Table(
        title=f"Plan: {plan.goal}",
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
        table.add_row(str(idx), Text(marker, style=style), step.description)
    return table


# ---------------------------------------------------------------------------
# Compact activity rendering
# ---------------------------------------------------------------------------


def _activity_line(event: ProgressEvent) -> Text | None:
    """Produce a compact one-liner for an activity event, or None to skip."""
    etype = event.type

    if etype == ProgressEventType.TOOL_START:
        label = event.tool_name or "tool"
        return Text.assemble(("  . ", "dim"), (f"Using {label}", "blue"))

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
        return Text.assemble(("  ", ""), (f"[{tag}] ", "bold magenta"), (event.summary or "started", ""))

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
# Input helpers
# ---------------------------------------------------------------------------


def read_user_input(console: Console, mode: str = "agent") -> str | None:
    """Read user input with backslash continuation for multiline.

    Returns None on EOF/interrupt (signals exit).
    """
    lines: list[str] = []
    prompt_str = f"[bold cyan]noe|{mode}>[/bold cyan] "
    continuation_str = "[dim]...[/dim]  "

    try:
        first = Prompt.ask(prompt_str, console=console, show_default=False)
    except (EOFError, KeyboardInterrupt):
        return None

    if first.endswith("\\"):
        lines.append(first[:-1])
        while True:
            try:
                cont = Prompt.ask(continuation_str, console=console, show_default=False)
            except (EOFError, KeyboardInterrupt):
                break
            if cont.endswith("\\"):
                lines.append(cont[:-1])
            else:
                lines.append(cont)
                break
        return "\n".join(lines)
    return first


# ---------------------------------------------------------------------------
# Async event-driven display loop
# ---------------------------------------------------------------------------


async def _process_query(
    agent: "NoeAgent",
    user_input: str,
    console: Console,
    session_logger: SessionLogger | None = None,
) -> "TaskPlan | None":
    """Process a single user query with compact Claude Code-style output."""
    from .state import TaskPlan

    current_plan: TaskPlan | None = None
    activity_lines: list[Text] = []
    partial_results: list[str] = []
    final_answer: str = ""
    current_step_summary: str = ""

    spinner = Spinner("dots", text="Thinking...", style="cyan")

    def _build_display() -> Group:
        """Assemble the live-updating renderable group."""
        parts: list[object] = []
        if current_plan:
            parts.append(render_plan_table(current_plan))
            parts.append(Text(""))
        if current_step_summary:
            parts.append(Text(f"  {current_step_summary}", style="bold"))
        for line in activity_lines[-15:]:
            parts.append(line)
        parts.append(Text(""))
        parts.append(spinner)
        return Group(*parts)

    from rich.live import Live

    with Live(_build_display(), console=console, refresh_per_second=8, transient=True):
        async for event in agent.astream_progress(user_input):
            etype = event.type

            if etype == ProgressEventType.PLAN_CREATED:
                if event.plan_snapshot:
                    current_plan = TaskPlan(**event.plan_snapshot)

            elif etype == ProgressEventType.PLAN_REVISED:
                if event.plan_snapshot:
                    current_plan = TaskPlan(**event.plan_snapshot)

            elif etype == ProgressEventType.STEP_START:
                current_step_summary = event.summary or ""
                if current_plan and event.step_index is not None:
                    idx = event.step_index
                    if idx < len(current_plan.steps):
                        current_plan.steps[idx].status = "in_progress"

            elif etype == ProgressEventType.STEP_COMPLETE:
                if current_plan and event.step_index is not None:
                    idx = event.step_index
                    if idx < len(current_plan.steps):
                        current_plan.steps[idx].status = "completed"

            elif etype in (
                ProgressEventType.TOOL_START,
                ProgressEventType.TOOL_END,
                ProgressEventType.SUBAGENT_START,
                ProgressEventType.SUBAGENT_PROGRESS,
                ProgressEventType.SUBAGENT_END,
                ProgressEventType.THINKING,
                ProgressEventType.ERROR,
            ):
                line = _activity_line(event)
                if line:
                    activity_lines.append(line)

            elif etype == ProgressEventType.PARTIAL_RESULT:
                if event.text:
                    partial_results.append(event.text)

            elif etype == ProgressEventType.TEXT_CHUNK:
                pass

            elif etype == ProgressEventType.REFLECTION:
                activity_lines.append(Text.assemble(("  . ", "dim"), ("Reflected on progress", "dim italic")))

            elif etype == ProgressEventType.FINAL_ANSWER:
                final_answer = event.text or ""

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
    """Launch the interactive Rich TUI for NoeAgent."""
    console = Console()
    current_plan: "TaskPlan | None" = None

    session_logger: SessionLogger | None = None
    if agent.config.enable_session_logging:
        session_logger = SessionLogger(log_dir=agent.config.session_log_dir)
        if session_logger not in agent.config.progress_callbacks:
            agent.config.progress_callbacks.append(session_logger)

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
            user_input = read_user_input(console, mode=agent.config.mode.value)
            if user_input is None:
                console.print("\n[dim]Goodbye.[/dim]")
                break

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
                current_plan = loop.run_until_complete(
                    _process_query(agent, user_input, console, session_logger=session_logger)
                )
            except Exception as exc:
                console.print(Text(f"  ! {exc}", style="bold red"))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Unified entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for NoeAgent TUI."""
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
    except ImportError:
        pass

    import os

    from noesium.core.utils.logging import setup_logging

    log_file = os.getenv("NOESIUM_TUI_LOG_FILE")
    setup_logging(
        level="WARNING",
        log_file=log_file,
        log_file_level="DEBUG",
        enable_colors=False,
        third_party_level="ERROR",
    )

    from .agent import NoeAgent

    agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, interface_mode="tui"))
    run_agent_tui(agent)


if __name__ == "__main__":
    main()
