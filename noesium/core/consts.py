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

# Default directories under NOESIUM_HOME
NOESIUM_LOGS_DIR = NOESIUM_HOME / "logs"
NOESIUM_MEMORY_DIR = NOESIUM_HOME / "memory"
NOESIUM_DATA_DIR = NOESIUM_HOME / "data"
NOESIUM_SESSIONS_DIR = NOESIUM_HOME / "sessions"

# Library temp/cache base (toolkits default here when used standalone)
NOESIUM_TMP_BASE = Path("/tmp/noesium")


def get_toolkit_tmp_dir(toolkit_name: str, subdir: str = "") -> str:
    """Return toolkit temp dir under NOESIUM_TMP_BASE, optionally with a subdir."""
    base = NOESIUM_TMP_BASE / toolkit_name
    if subdir:
        base = base / subdir
    return str(base)
