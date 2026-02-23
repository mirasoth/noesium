import asyncio
import logging
import os
from typing import TYPE_CHECKING

from noesium.agents.browser_use.logging_config import setup_logging

# Import BrowserUseAgent directly (not lazy)
from .agent import BrowserUseAgent

# Only set up logging if not in MCP mode or if explicitly requested
if os.environ.get("BROWSER_USE_SETUP_LOGGING", "true").lower() != "false":
    from noesium.agents.browser_use.config import CONFIG

    # Get log file paths from config/environment
    debug_log_file = getattr(CONFIG, "BROWSER_USE_DEBUG_LOG_FILE", None)
    info_log_file = getattr(CONFIG, "BROWSER_USE_INFO_LOG_FILE", None)

    # Set up logging with file handlers if specified
    logger = setup_logging(debug_log_file=debug_log_file, info_log_file=info_log_file)
else:
    logger = logging.getLogger("browser_use")

# Monkeypatch BaseSubprocessTransport.__del__ to handle closed event loops gracefully
_original_del = asyncio.base_subprocess.BaseSubprocessTransport.__del__


def _patched_del(self):
    """Patched __del__ handling closed event loops gracefully"""
    try:
        # Check if the event loop is closed before calling the original
        if hasattr(self, "_loop") and self._loop and self._loop.is_closed():
            # Event loop is closed, skip cleanup that requires the loop
            return
        _original_del(self)
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            # Silently ignore this specific error
            pass
        else:
            raise


asyncio.base_subprocess.BaseSubprocessTransport.__del__ = _patched_del


# Type stubs for lazy imports - fixes linter warnings
if TYPE_CHECKING:
    from noesium.agents.browser_use.agent.prompts import SystemPrompt
    from noesium.agents.browser_use.agent.service import Agent
    from noesium.agents.browser_use.agent.views import ActionModel, ActionResult, AgentHistoryList
    from noesium.agents.browser_use.browser import BrowserProfile
    from noesium.agents.browser_use.browser import BrowserSession
    from noesium.agents.browser_use.browser import BrowserSession as Browser
    from noesium.agents.browser_use.dom.service import DomService
    from noesium.agents.browser_use.tools.service import Controller, Tools


# Lazy imports mapping - only import when actually accessed
_LAZY_IMPORTS = {
    # Agent service (heavy due to dependencies)
    "Agent": ("noesium.agents.browser_use.agent.service", "Agent"),
    # System prompt (moderate weight due to agent.views imports)
    "SystemPrompt": ("noesium.agents.browser_use.agent.prompts", "SystemPrompt"),
    # Agent views (very heavy - over 1 second!)
    "ActionModel": ("noesium.agents.browser_use.agent.views", "ActionModel"),
    "ActionResult": ("noesium.agents.browser_use.agent.views", "ActionResult"),
    "AgentHistoryList": ("noesium.agents.browser_use.agent.views", "AgentHistoryList"),
    "BrowserSession": ("noesium.agents.browser_use.browser", "BrowserSession"),
    "Browser": ("noesium.agents.browser_use.browser", "BrowserSession"),  # Alias for BrowserSession
    "BrowserProfile": ("noesium.agents.browser_use.browser", "BrowserProfile"),
    # Tools (moderate weight)
    "Tools": ("noesium.agents.browser_use.tools.service", "Tools"),
    "Controller": ("noesium.agents.browser_use.tools.service", "Controller"),  # alias
    # DOM service (moderate weight)
    "DomService": ("noesium.agents.browser_use.dom.service", "DomService"),
}


def __getattr__(name: str):
    """Lazy import mechanism - only import modules when they're actually accessed."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        try:
            from importlib import import_module

            module = import_module(module_path)
            if attr_name is None:
                # For modules like 'models', return the module itself
                attr = module
            else:
                attr = getattr(module, attr_name)
            # Cache the imported attribute in the module's globals
            globals()[name] = attr
            return attr
        except ImportError as e:
            raise ImportError(f"Failed to import {name} from {module_path}: {e}") from e

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "Agent",
    "BrowserSession",
    "Browser",  # Alias for BrowserSession
    "BrowserProfile",
    "Controller",
    "DomService",
    "SystemPrompt",
    "ActionResult",
    "ActionModel",
    "AgentHistoryList",
    "Tools",
    "Controller",
    "BrowserUseAgent",  # Noesium wrapper
]
