"""Path utilities for Voyager."""

from pathlib import Path


def get_data_root() -> Path:
    """Get the root data directory for Voyager."""
    data_root = Path.home() / ".voyager"
    data_root.mkdir(parents=True, exist_ok=True)
    return data_root


def get_workspace_root() -> Path:
    """Get the workspace directory for cloned repositories."""
    workspace = get_data_root() / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def get_tasks_dir() -> Path:
    """Get the tasks directory for task storage."""
    tasks_dir = get_data_root() / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir
