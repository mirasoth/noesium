"""Global constants for the Noesium framework."""

from pathlib import Path

# LLM Model Constants
GEMINI_PRO = "google/gemini-2.5-pro"
GEMINI_FLASH = "google/gemini-2.5-flash"

# Embedding Constants
DEFAULT_EMBEDDING_DIMS = 768

# Configuration Constants
NOE_AGENT_HOME = Path.home() / ".noeagent"
FRAMEWORK_HOME = NOE_AGENT_HOME  # Alias for clarity (RFC-1007)
DEFAULT_CONFIG_PATH = FRAMEWORK_HOME / "config.json"
CONFIG_VERSION = "1.0"

# Default Directories
NOE_AGENT_LOGS_DIR = FRAMEWORK_HOME / "logs"
NOE_AGENT_MEMORY_DIR = FRAMEWORK_HOME / "memory"
NOE_AGENT_DATA_DIR = FRAMEWORK_HOME / "data"
NOE_AGENT_SESSIONS_DIR = FRAMEWORK_HOME / "sessions"

# Library temp/cache base (toolkits default here when used standalone)
NOE_TMP_BASE = Path("/tmp/noesium")


def get_toolkit_tmp_dir(toolkit_name: str, subdir: str = "") -> str:
    """Return toolkit temp dir under NOE_TMP_BASE, optionally with a subdir."""
    base = NOE_TMP_BASE / toolkit_name
    if subdir:
        base = base / subdir
    return str(base)
