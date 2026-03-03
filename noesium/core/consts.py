"""Global constants for NoeAgent"""

from pathlib import Path

# LLM Model Constants
GEMINI_PRO = "google/gemini-2.5-pro"
GEMINI_FLASH = "google/gemini-2.5-flash"

# Embedding Constants
DEFAULT_EMBEDDING_DIMS = 768

# Configuration Constants
NOE_AGENT_HOME = Path.home() / ".noeagent"
DEFAULT_CONFIG_PATH = NOE_AGENT_HOME / "config.json"
CONFIG_VERSION = "1.0"

# Default Directories
NOE_AGENT_LOGS_DIR = NOE_AGENT_HOME / "logs"
NOE_AGENT_MEMORY_DIR = NOE_AGENT_HOME / "memory"
NOE_AGENT_DATA_DIR = NOE_AGENT_HOME / "data"
NOE_AGENT_SESSIONS_DIR = NOE_AGENT_HOME / "sessions"
