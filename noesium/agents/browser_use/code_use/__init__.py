"""Code-use mode - Jupyter notebook-like code execution for browser automation."""

from noesium.agents.browser_use.code_use.namespace import create_namespace
from noesium.agents.browser_use.code_use.notebook_export import export_to_ipynb, session_to_python_script
from noesium.agents.browser_use.code_use.service import CodeAgent
from noesium.agents.browser_use.code_use.views import CodeCell, ExecutionStatus, NotebookSession

__all__ = [
    "CodeAgent",
    "create_namespace",
    "export_to_ipynb",
    "session_to_python_script",
    "CodeCell",
    "ExecutionStatus",
    "NotebookSession",
]
