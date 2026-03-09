"""Entry point for NoeAgent CLI.

Usage:
    noeagent                       Launch TUI interface
    noeagent --autonomous          Run in autonomous mode
    noeagent --autonomous --goal "Monitor issues"  Autonomous with initial goal
    noeagent config path           Show config file path
    noeagent config show [-k KEY]  Show current config
    noeagent config init [--provider PROVIDER]  Initialize config
    noeagent config set KEY VALUE  Set config value
    python -m noeagent
"""

import argparse
import json
import sys

import dotenv

dotenv.load_dotenv()


def main() -> None:
    """Main entry point for noeagent CLI command."""
    parser = argparse.ArgumentParser(
        prog="noeagent",
        description="NoeAgent - An intelligent agent framework",
    )

    # Add global options for autonomous mode
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Run in autonomous mode (RFC-1005)",
    )
    parser.add_argument(
        "--goal",
        type=str,
        help="Initial goal for autonomous mode",
    )
    parser.add_argument(
        "--tick-interval",
        type=float,
        default=10.0,
        help="Cognitive loop tick interval in seconds (default: 10.0)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", help="Config commands"
    )

    # config path
    config_subparsers.add_parser("path", help="Show config file path")

    # config show
    show_parser = config_subparsers.add_parser(
        "show", help="Show current configuration"
    )
    show_parser.add_argument(
        "-k", "--key", help="Config key to show (e.g., llm.provider)"
    )

    # config init
    init_parser = config_subparsers.add_parser(
        "init", help="Initialize config file with defaults"
    )
    init_parser.add_argument(
        "-p", "--provider", help="LLM provider name (e.g., openai, openrouter, ollama)"
    )

    # config set
    set_parser = config_subparsers.add_parser("set", help="Set a configuration value")
    set_parser.add_argument("key", help="Config key (e.g., llm.provider)")
    set_parser.add_argument("value", help="Config value (JSON or string)")

    args = parser.parse_args()

    # Route to appropriate handler
    if args.command == "config":
        handle_config_command(args)
    elif args.autonomous:
        # Run in autonomous mode
        launch_autonomous(args.goal, args.tick_interval)
    else:
        # Default: launch TUI
        launch_tui()


def handle_config_command(args: argparse.Namespace) -> None:
    """Handle config subcommands."""
    if args.config_command == "path":
        cmd_config_path()
    elif args.config_command == "show":
        cmd_config_show(args.key)
    elif args.config_command == "init":
        cmd_config_init(args.provider)
    elif args.config_command == "set":
        cmd_config_set(args.key, args.value)
    else:
        print("Error: Missing config command. Use: path, show, init, or set")
        sys.exit(1)


def cmd_config_path() -> None:
    """Show config file path."""
    try:
        from noeagent.config import get_noe_config_path

        print(str(get_noe_config_path()))
    except ImportError:
        from pathlib import Path

        print(str(Path.home() / ".noeagent" / "config.json"))


def cmd_config_show(key: str | None = None) -> None:
    """Show current configuration.

    Args:
        key: Optional config key to show (e.g., llm.provider)
    """
    try:
        from noeagent.config import get_noe_config_path

        from noesium.core.config import load_config

        config = load_config(get_noe_config_path())

        if key:
            # Navigate nested keys
            value = config.model_dump()
            for k in key.split("."):
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    value = None
                    break

            if value is None:
                print(f"Key '{key}' not found")
                sys.exit(1)
            else:
                print(json.dumps(value, indent=2))
        else:
            print(json.dumps(config.model_dump(exclude_none=True), indent=2))
    except ImportError as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_init(provider: str | None = None) -> None:
    """Initialize config file with defaults.

    Args:
        provider: Optional LLM provider name to set as default
    """
    try:
        from noeagent.config import get_noe_config_path

        from noesium.core.config import FrameworkConfig, save_config

        config_path = get_noe_config_path()

        if config_path.exists():
            response = input(
                f"Config file already exists at {config_path}. Overwrite? [y/N] "
            )
            if response.lower() != "y":
                print("Aborted.")
                return

        config = FrameworkConfig()
        if provider:
            config.llm.provider = provider

        save_config(config, config_path)
        print(f"Created config file at {config_path}")
    except ImportError as e:
        print(f"Error initializing config: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_set(key: str, value: str) -> None:
    """Set a configuration value.

    Args:
        key: Config key (e.g., llm.provider)
        value: Config value (JSON or string)
    """
    try:
        from noeagent.config import get_noe_config_path

        from noesium.core.config import FrameworkConfig, load_config, save_config

        config = load_config(get_noe_config_path())

        # Parse key path
        keys = key.split(".")
        data = config.model_dump()

        # Navigate to parent
        obj = data
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})

        # Set value (try to parse as JSON, otherwise use string)
        try:
            obj[keys[-1]] = json.loads(value)
        except json.JSONDecodeError:
            obj[keys[-1]] = value

        # Save
        config = FrameworkConfig(**data)
        save_config(config, get_noe_config_path())
        print(f"Set {key} = {value}")
    except ImportError as e:
        print(f"Error setting config: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def launch_tui() -> None:
    """Launch the TUI interface."""
    try:
        from noeagent.tui import main as tui_main

        tui_main()
    except ImportError as e:
        _handle_import_error(e)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting NoeAgent: {e}", file=sys.stderr)
        sys.exit(1)


def launch_autonomous(initial_goal: str | None, tick_interval: float) -> None:
    """Launch NoeAgent in autonomous mode.

    Args:
        initial_goal: Optional initial goal for autonomous mode
        tick_interval: Cognitive loop tick interval in seconds
    """
    try:
        import asyncio

        from noeagent.agent import NoeAgent
        from noeagent.autonomous import run_autonomous_mode
        from noeagent.config import get_noe_config_path

        from noesium.core.config import load_config

        print("🤖 Starting NoeAgent in autonomous mode...")
        print(f"   Tick interval: {tick_interval}s")
        if initial_goal:
            print(f"   Initial goal: {initial_goal}")
        print()

        # Load config and initialize agent
        config_path = get_noe_config_path()
        config = load_config(config_path)

        # Create NoeAgent instance
        agent = NoeAgent(config=config)

        # Run autonomous mode
        asyncio.run(run_autonomous_mode(agent, initial_goal))

    except ImportError as e:
        _handle_import_error(e)
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting autonomous mode: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def _handle_import_error(error: ImportError) -> None:
    """Provide helpful error messages for missing dependencies."""
    error_name = str(error).lower()

    # Check for specific missing dependencies
    if "langchain" in error_name or "langgraph" in error_name:
        print(
            "Error: Missing required dependencies for NoeAgent.\n"
            "\n"
            "Please install the agents extra:\n"
            "  pip install noesium[agents]\n"
            "\n"
            "Or install langchain and langgraph directly:\n"
            "  pip install langchain-core langgraph",
            file=sys.stderr,
        )
    elif "rich" in error_name:
        print(
            "Error: Missing 'rich' package for TUI interface.\n"
            "\n"
            "Please install it:\n"
            "  pip install rich",
            file=sys.stderr,
        )
    elif "pydantic" in error_name:
        print(
            "Error: Missing 'pydantic' package.\n"
            "\n"
            "Please install it:\n"
            "  pip install pydantic",
            file=sys.stderr,
        )
    else:
        print(
            f"Error: Missing dependency: {error}\n"
            "\n"
            "Please ensure all required dependencies are installed:\n"
            "  pip install noesium[agents]",
            file=sys.stderr,
        )

    sys.exit(1)


if __name__ == "__main__":
    main()
