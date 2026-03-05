"""Global constants for the Noesium framework (RFC-1007: no application-specific names)."""

import os
from pathlib import Path

# LLM Model Constants
GEMINI_PRO = "google/gemini-2.5-pro"
GEMINI_FLASH = "google/gemini-2.5-flash"

# Embedding Constants
DEFAULT_EMBEDDING_DIMS = 768

# Framework home: NOESIUM_HOME env or ~/.noesium (application layers may use their own paths)
NOESIUM_HOME = Path(os.getenv("NOESIUM_HOME", str(Path.home() / ".noesium")))
DEFAULT_CONFIG_PATH = NOESIUM_HOME / "config.json"
CONFIG_VERSION = "1.0"

# Library temp/cache base (toolkits default here when used standalone)
NOESIUM_TMP_BASE = Path("/tmp/noesium")


def get_toolkit_tmp_dir(toolkit_name: str, subdir: str = "") -> str:
    """Return toolkit temp dir under NOESIUM_TMP_BASE, optionally with a subdir."""
    base = NOESIUM_TMP_BASE / toolkit_name
    if subdir:
        base = base / subdir
    return str(base)


def set_noesium_home(path: str | Path) -> None:
    """Override NOESIUM_HOME and update dependent paths.

    This is called by application layers to use their own
    home directory instead of the default ~/.noesium.

    Must be called before any other noesium imports that use NOESIUM_HOME.

    Args:
        path: New home directory path (e.g., ~/.my-agent)
    """
    global NOESIUM_HOME, DEFAULT_CONFIG_PATH

    NOESIUM_HOME = Path(path)
    DEFAULT_CONFIG_PATH = NOESIUM_HOME / "config.json"
