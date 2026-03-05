"""NoeCoder configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class NoeCoderConfig(BaseModel):
    """NoeCoder configuration."""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Paths
    data_root: Path = Field(default_factory=lambda: Path.home() / ".noecoder")

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
    commit_message_prefix: str = "[NoeCoder] "

    # UI settings
    theme: str = "dark"
    show_thinking: bool = True
    show_tool_details: bool = True

    # Override from env vars if set
    model_config = {"extra": "ignore"}

    @classmethod
    def from_env(cls) -> "NoeCoderConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("NOECODER_HOST", "127.0.0.1"),
            port=int(os.getenv("NOECODER_PORT", "8000")),
            debug=os.getenv("NOECODER_DEBUG", "false").lower() == "true",
            data_root=Path(os.getenv("NOECODER_DATA_ROOT", str(Path.home() / ".noecoder"))),
            llm_provider=os.getenv("NOECODER_LLM_PROVIDER", "openai"),
            llm_model=os.getenv("NOECODER_LLM_MODEL"),
            max_iterations=int(os.getenv("NOECODER_MAX_ITERATIONS", "25")),
            reflection_interval=int(os.getenv("NOECODER_REFLECTION_INTERVAL", "3")),
            max_concurrent_tasks=int(os.getenv("NOECODER_MAX_CONCURRENT_TASKS", "1")),
            task_timeout_seconds=int(os.getenv("NOECODER_TASK_TIMEOUT_SECONDS", "600")),
            default_branch=os.getenv("NOECODER_DEFAULT_BRANCH", "main"),
            auto_commit=os.getenv("NOECODER_AUTO_COMMIT", "true").lower() == "true",
            commit_message_prefix=os.getenv("NOECODER_COMMIT_MESSAGE_PREFIX", "[NoeCoder] "),
            theme=os.getenv("NOECODER_THEME", "dark"),
            show_thinking=os.getenv("NOECODER_SHOW_THINKING", "true").lower() == "true",
            show_tool_details=os.getenv("NOECODER_SHOW_TOOL_DETAILS", "true").lower() == "true",
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
    def load(cls, config_path: Path | None = None) -> "NoeCoderConfig":
        """Load configuration from file or return defaults."""
        if config_path is None:
            config_path = Path.home() / ".noecoder" / "config.json"

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
