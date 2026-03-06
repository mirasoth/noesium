"""State Manager for file-based persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiofiles
from voyager.models.events import ProgressEventData
from voyager.models.repository import Repository
from voyager.models.task import Task, TaskStatus


class StateManager:
    """File-based state persistence for Voyager."""

    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.tasks_dir = data_root / "tasks"
        self.workspace_dir = data_root / "workspace"
        self.logs_dir = data_root / "logs"

        # Ensure directories exist
        for d in [self.tasks_dir, self.workspace_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # --- Task Operations ---

    async def save_task(self, task: Task) -> None:
        """Save task to JSON file."""
        path = self.tasks_dir / f"{task.task_id}.json"
        async with aiofiles.open(path, "w") as f:
            await f.write(task.model_dump_json(indent=2))

    async def get_task(self, task_id: str) -> Task | None:
        """Load task from JSON file."""
        path = self.tasks_dir / f"{task_id}.json"
        if not path.exists():
            return None
        async with aiofiles.open(path) as f:
            data = await f.read()
        return Task.model_validate_json(data)

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        repository_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filtering."""
        tasks = []
        task_files = sorted(
            self.tasks_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for path in task_files:
            task = await self.get_task(path.stem)
            if task is None:
                continue
            if status and task.status != status:
                continue
            if repository_id and task.repository_id != repository_id:
                continue
            tasks.append(task)
            if len(tasks) >= limit + offset:
                break

        return tasks[offset : offset + limit]

    async def delete_task(self, task_id: str) -> bool:
        """Delete task and its event log."""
        task_path = self.tasks_dir / f"{task_id}.json"
        events_path = self.tasks_dir / f"{task_id}-events.jsonl"

        deleted = False
        if task_path.exists():
            task_path.unlink()
            deleted = True
        if events_path.exists():
            events_path.unlink()
        return deleted

    # --- Event Logging ---

    async def append_event(self, task_id: str, event: ProgressEventData) -> None:
        """Append event to task's event log (JSONL format)."""
        path = self.tasks_dir / f"{task_id}-events.jsonl"
        async with aiofiles.open(path, "a") as f:
            await f.write(event.model_dump_json() + "\n")

    async def get_events(self, task_id: str, limit: int = 100) -> list[ProgressEventData]:
        """Read events from task's event log."""
        path = self.tasks_dir / f"{task_id}-events.jsonl"
        if not path.exists():
            return []

        events = []
        async with aiofiles.open(path) as f:
            async for line in f:
                line = line.strip()
                if line:
                    events.append(ProgressEventData.model_validate_json(line))

        return events[-limit:]

    # --- Repository Operations ---

    async def save_repository(self, repo: Repository) -> None:
        """Save repository to registry."""
        path = self.data_root / "repositories.json"

        repos = await self.list_repositories()
        # Update or add
        existing = next((r for r in repos if r.id == repo.id), None)
        if existing:
            repos.remove(existing)
        repos.append(repo)

        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps([r.model_dump() for r in repos], indent=2, default=str))

    async def get_repository(self, repo_id: str) -> Repository | None:
        """Get repository by ID."""
        repos = await self.list_repositories()
        return next((r for r in repos if r.id == repo_id), None)

    async def list_repositories(self) -> list[Repository]:
        """List all repositories."""
        path = self.data_root / "repositories.json"
        if not path.exists():
            return []
        async with aiofiles.open(path) as f:
            data = json.loads(await f.read())
        return [Repository(**r) for r in data]

    async def delete_repository(self, repo_id: str) -> bool:
        """Remove repository from registry."""
        repos = await self.list_repositories()
        filtered = [r for r in repos if r.id != repo_id]
        if len(filtered) == len(repos):
            return False

        path = self.data_root / "repositories.json"
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps([r.model_dump() for r in filtered], indent=2, default=str))
        return True

    # --- Configuration ---

    async def save_config(self, config: dict[str, Any]) -> None:
        """Save global configuration."""
        path = self.data_root / "config.json"
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(config, indent=2, default=str))

    async def load_config(self) -> dict[str, Any]:
        """Load global configuration."""
        path = self.data_root / "config.json"
        if not path.exists():
            return {}
        async with aiofiles.open(path) as f:
            return json.loads(await f.read())
