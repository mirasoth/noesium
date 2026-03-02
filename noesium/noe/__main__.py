"""Entry point for NoeAgent CLI.

Usage:
    noe-agent
    python -m noesium.noe
"""

import sys


def main() -> None:
    """Main entry point for noe-agent CLI command."""
    try:
        from noesium.noe.tui import main as tui_main

        tui_main()
    except ImportError as e:
        _handle_import_error(e)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting NoeAgent: {e}", file=sys.stderr)
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
            "Error: Missing 'rich' package for TUI interface.\n" "\n" "Please install it:\n" "  pip install rich",
            file=sys.stderr,
        )
    elif "pydantic" in error_name:
        print(
            "Error: Missing 'pydantic' package.\n" "\n" "Please install it:\n" "  pip install pydantic",
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
