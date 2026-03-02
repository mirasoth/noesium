"""Rich-based terminal UI for NoeAgent.

Provides a Claude Code-style interactive CLI with:
  * Streaming markdown output
  * Live spinner during LLM / tool calls
  * Collapsible tool-call panels
  * Live-updating todo/plan table
  * Slash commands for mode switching, plan display, memory stats
  * Multiline input (backslash continuation)
  * Styled error panels
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from .agent import NoeAgent
    from .state import TaskPlan

from .config import NoeConfig, NoeMode

# ---------------------------------------------------------------------------
# Plan rendering
# ---------------------------------------------------------------------------


def render_plan_table(plan: "TaskPlan") -> Table:
    """Build a Rich Table from a TaskPlan."""
    table = Table(
        title=f"Plan: {plan.goal}",
        title_style="bold cyan",
        show_lines=True,
        expand=False,
        min_width=50,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Status", width=12)
    table.add_column("Step", ratio=1)

    status_style = {
        "pending": ("[ ]", "dim"),
        "in_progress": ("[>]", "bold yellow"),
        "completed": ("[x]", "green"),
        "failed": ("[!]", "bold red"),
    }

    for idx, step in enumerate(plan.steps, start=1):
        marker, style = status_style.get(step.status, ("[ ]", "dim"))
        table.add_row(str(idx), Text(marker, style=style), step.description)
    return table


def render_tool_call_panel(name: str, args: dict, *, result: str | None = None) -> Panel:
    """Render a tool call as a styled Panel."""
    body_parts: list[str] = []
    if args:
        try:
            body_parts.append(json.dumps(args, indent=2, default=str)[:1500])
        except TypeError:
            body_parts.append(str(args)[:1500])
    if result is not None:
        body_parts.append(f"\n--- result ---\n{result[:2000]}")
    body = "\n".join(body_parts) or "(no arguments)"
    return Panel(body, title=f"Tool: {name}", border_style="blue", expand=False)


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
}


def handle_slash_command(
    cmd: str,
    agent: "NoeAgent",
    console: Console,
    *,
    current_plan: "TaskPlan | None" = None,
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


async def _process_query(agent: "NoeAgent", user_input: str, console: Console) -> "TaskPlan | None":
    """Process a single user query through astream_events with Rich output."""
    current_plan: TaskPlan | None = None
    pending_tool_calls: dict[str, dict] = {}
    response_text: list[str] = []
    final_answer: str = ""

    spinner = Spinner("dots", text="Thinking...", style="cyan")
    with Live(spinner, console=console, refresh_per_second=8, transient=True):
        async for event in agent.astream_events(user_input):
            etype = event.get("type", "")

            if etype == "plan_created":
                current_plan = event["plan"]

            elif etype == "step_started":
                spinner.update(text=f"Step {event['index'] + 1}: {event['step']}")
                if current_plan:
                    step = current_plan.steps[event["index"]] if event["index"] < len(current_plan.steps) else None
                    if step:
                        step.status = "in_progress"

            elif etype == "tool_call_started":
                name = event["name"]
                args = event.get("args", {})
                pending_tool_calls[name] = args
                spinner.update(text=f"Executing tool: {name}")

            elif etype == "tool_call_completed":
                name = event["name"]
                result = event.get("result", "")
                args = pending_tool_calls.pop(name, {})
                console.print(render_tool_call_panel(name, args, result=result))

            elif etype == "thinking":
                spinner.update(text=event.get("thought", "Thinking..."))

            elif etype == "text_chunk":
                text = event.get("text", "")
                if text:
                    response_text.append(text)

            elif etype == "final_answer":
                final_answer = event.get("text", "")

            elif etype == "reflection":
                console.print(
                    Panel(
                        event["text"],
                        title="Reflection",
                        border_style="yellow",
                        expand=False,
                    )
                )

    # Display plan if one was created
    if current_plan:
        console.print(render_plan_table(current_plan))

    # Display the response
    if final_answer:
        console.print()
        console.print(Markdown(final_answer))
        console.print()
    elif response_text:
        console.print()
        console.print(Markdown("".join(response_text)))
        console.print()

    return current_plan


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------


def run_agent_tui(agent: "NoeAgent") -> None:
    """Launch the interactive Rich TUI for NoeAgent."""
    console = Console()
    current_plan: TaskPlan | None = None

    console.print(
        Panel(
            "[bold]NoeAgent[/bold] — Autonomous Research Assistant\n"
            f"Mode: [cyan]{agent.config.mode.value}[/cyan]  |  "
            "Type [bold cyan]/help[/bold cyan] for commands, "
            "[bold cyan]/exit[/bold cyan] to quit.",
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
                should_exit = handle_slash_command(user_input, agent, console, current_plan=current_plan)
                if should_exit:
                    break
                continue

            console.print()

            try:
                current_plan = loop.run_until_complete(_process_query(agent, user_input, console))
            except Exception as exc:
                console.print(
                    Panel(
                        str(exc),
                        title="Error",
                        border_style="red",
                        expand=False,
                    )
                )

            # Print the final answer as markdown
            if agent.graph:
                try:
                    state = agent.graph.get_state(config={}).values
                    final = state.get("final_answer", "")
                    if final:
                        console.print()
                        console.print(Markdown(final))
                        console.print()
                except Exception:
                    pass
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Unified entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for NoeAgent TUI."""
    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
    except ImportError:
        pass

    # Configure logging for TUI mode - suppress INFO logs to keep UI clean
    import os

    from noesium.core.utils.logging import setup_logging

    # In TUI mode, only show WARNING+ in console, but allow DEBUG in log file
    # Set NOESIUM_TUI_LOG_FILE to enable file logging (e.g., "noe_debug.log")
    log_file = os.getenv("NOESIUM_TUI_LOG_FILE")
    setup_logging(
        level="WARNING",  # Console: only warnings and errors
        log_file=log_file,  # Optional: log to file if specified
        log_file_level="DEBUG",  # File: capture everything
        enable_colors=False,  # Disable colors to avoid interfering with Rich
        third_party_level="ERROR",  # Suppress third-party library INFO/WARNING
    )

    from .agent import NoeAgent

    agent = NoeAgent(NoeConfig(mode=NoeMode.AGENT, interface_mode="tui"))
    run_agent_tui(agent)


if __name__ == "__main__":
    main()
