"""Voyager configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class VoyagerConfig(BaseModel):
    """Voyager configuration."""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Paths
    data_root: Path = Field(default_factory=lambda: Path.home() / ".voyager")

    # NoeAgent defaults
    llm_provider: str = "openai"
    llm_model: str | None = None
    max_iterations: int = 25
    reflection_interval: int = 3

    # Task settings
    max_concurrent_tasks: int = 1
    task_timeout_seconds: int = 600

    # Git settings
    default_branch: str = "main"
    auto_commit: bool = True
    commit_message_prefix: str = "[Voyager] "

    # UI settings
    theme: str = "dark"
    show_thinking: bool = True
    show_tool_details: bool = True

    # Override from env vars if set
    model_config = {"extra": "ignore"}

    @classmethod
    def from_env(cls) -> "VoyagerConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("VOYAGER_HOST", "127.0.0.1"),
            port=int(os.getenv("VOYAGER_PORT", "8000")),
            debug=os.getenv("VOYAGER_DEBUG", "false").lower() == "true",
            data_root=Path(os.getenv("VOYAGER_DATA_ROOT", str(Path.home() / ".voyager"))),
            llm_provider=os.getenv("VOYAGER_LLM_PROVIDER", "openai"),
            llm_model=os.getenv("VOYAGER_LLM_MODEL"),
            max_iterations=int(os.getenv("VOYAGER_MAX_ITERATIONS", "25")),
            reflection_interval=int(os.getenv("VOYAGER_REFLECTION_INTERVAL", "3")),
            max_concurrent_tasks=int(os.getenv("VOYAGER_MAX_CONCURRENT_TASKS", "1")),
            task_timeout_seconds=int(os.getenv("VOYAGER_TASK_TIMEOUT_SECONDS", "600")),
            default_branch=os.getenv("VOYAGER_DEFAULT_BRANCH", "main"),
            auto_commit=os.getenv("VOYAGER_AUTO_COMMIT", "true").lower() == "true",
            commit_message_prefix=os.getenv("VOYAGER_COMMIT_MESSAGE_PREFIX", "[Voyager] "),
            theme=os.getenv("VOYAGER_THEME", "dark"),
            show_thinking=os.getenv("VOYAGER_SHOW_THINKING", "true").lower() == "true",
            show_tool_details=os.getenv("VOYAGER_SHOW_TOOL_DETAILS", "true").lower() == "true",
        )

    @property
    def workspace_root(self) -> Path:
        """Get the workspace directory for cloned repositories."""
        workspace = self.data_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    @property
    def tasks_dir(self) -> Path:
        """Get the tasks directory for task storage."""
        tasks = self.data_root / "tasks"
        tasks.mkdir(parents=True, exist_ok=True)
        return tasks

    @property
    def logs_dir(self) -> Path:
        """Get the logs directory."""
        logs = self.data_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        return logs

    def get_noe_config(self, working_directory: str | None = None) -> dict[str, Any]:
        """Create NoeConfig kwargs for NoeAgent instances."""
        return {
            "llm_provider": self.llm_provider,
            "model_name": self.llm_model,
            "max_iterations": self.max_iterations,
            "reflection_interval": self.reflection_interval,
            "working_directory": working_directory,
            "enabled_toolkits": [
                "bash",
                "file_edit",
                "python_executor",
                "document",
            ],
            "permissions": [
                "fs:read",
                "fs:write",
                "shell:execute",
                "net:outbound",
            ],
        }

    @classmethod
    def load(cls, config_path: Path | None = None) -> "VoyagerConfig":
        """Load configuration from file or return defaults."""
        if config_path is None:
            config_path = Path.home() / ".voyager" / "config.json"

        if config_path.exists():
            import json

            with open(config_path) as f:
                data = json.load(f)
            return cls(**data)
        return cls.from_env()

    def save(self, config_path: Path | None = None) -> None:
        """Save configuration to file."""
        if config_path is None:
            config_path = self.data_root / "config.json"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        import json

        with open(config_path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2, default=str)
