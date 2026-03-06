# Voyager Implementation Design

**Status**: Draft  
**Authors**: Noesium Team  
**Created**: 2026-03-04  
**Last Updated**: 2026-03-04  
**Depends on**: [RFC-9000](../specs/RFC-9000.md), [RFC-9001](../specs/RFC-9001.md)  
**Kind**: Implementation Design

---

## 1. Overview

This document defines the concrete implementation plan for Voyager, translating the design philosophy (RFC-9000) and architecture (RFC-9001) into actionable specifications.

**Important**: Voyager is implemented as **standalone projects** separate from the noesium core framework:
- `coder-backend/` - Standalone Python backend project
- `coder-frontend/` - Standalone React frontend project

Both projects depend on `noesium` as a package dependency but maintain their own codebases, configurations, and build processes.

### 1.1 Technology Stack

| Layer | Technology | Version | Rationale |
|-------|------------|---------|-----------|
| **Backend Framework** | FastAPI | >=0.109.0 | Async, typed, OpenAPI docs |
| **WebSocket** | python-socketio | >=5.11.0 | Auto-reconnect, room support |
| **Git Operations** | GitPython | >=3.1.0 | Programmatic git access |
| **State Persistence** | JSON/JSONL | - | Simple, human-readable |
| **Frontend Framework** | React + Vite | 18.x / 5.x | Modern SPA with fast HMR |
| **Frontend State** | React Query | 5.x | Server state management |
| **Styling** | TailwindCSS | 3.x | Utility-first CSS |
| **Code Editor** | Monaco Editor | 0.45+ | VS Code editor component |

### 1.2 Project Structure

```
workspace/
├── noesium/                    # Core framework (existing)
│   └── noesium/
│       ├── core/
│       ├── noeagent/
│       └── ...
│
├── coder-backend/              # Standalone backend project
│   ├── pyproject.toml          # Independent Python project config
│   ├── src/
│   │   └── voyager/
│   │       ├── __init__.py
│   │       ├── main.py         # FastAPI + SocketIO entry
│   │       ├── config.py       # VoyagerConfig
│   │       ├── api/
│   │       │   ├── __init__.py
│   │       │   ├── repositories.py
│   │       │   ├── tasks.py
│   │       │   ├── config.py
│   │       │   └── websocket.py
│   │       ├── services/
│   │       │   ├── __init__.py
│   │       │   ├── task_orchestrator.py
│   │       │   ├── git_client.py
│   │       │   ├── state_manager.py
│   │       │   └── session_manager.py
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   ├── repository.py
│   │       │   ├── task.py
│   │       │   └── events.py
│   │       └── utils/
│   │           ├── __init__.py
│   │           └── paths.py
│   └── tests/
│
└── coder-frontend/             # Standalone frontend project
    ├── package.json            # Independent Node.js project config
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── components/
        │   ├── layout/
        │   ├── tasks/
        │   ├── code/
        │   └── progress/
        ├── hooks/
        ├── services/
        └── types/
```

---

## 2. Data Models

### 2.1 Core Entities

```python
# voyager/models/task.py

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStep(BaseModel):
    step_id: str = Field(default_factory=uuid7str)
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    result: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CodeChange(BaseModel):
    file_path: str
    change_type: str  # created, modified, deleted
    diff: str
    lines_added: int = 0
    lines_removed: int = 0


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=uuid7str)
    artifact_type: str  # code, document, image
    content: str | None = None
    file_path: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Task(BaseModel):
    task_id: str = Field(default_factory=uuid7str)
    title: str
    description: str
    status: TaskStatus = TaskStatus.CREATED
    repository_id: str | None = None
    branch: str | None = None
    
    # Execution state
    steps: list[TaskStep] = []
    current_step_index: int = 0
    
    # Results
    code_changes: list[CodeChange] = []
    artifacts: list[Artifact] = []
    final_answer: str | None = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    
    # Reasoning trace
    reasoning_trace: list[dict[str, Any]] = []
    tool_invocations: list[dict[str, Any]] = []
    
    # Error info
    error_message: str | None = None


class TaskCreate(BaseModel):
    """Request body for creating a task."""
    title: str | None = None  # Optional, derived from description
    description: str
    repository_id: str | None = None
    branch: str | None = None


class TaskUpdate(BaseModel):
    """Request body for updating a task."""
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
```

```python
# voyager/models/repository.py

from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from uuid_extensions import uuid7str


class Repository(BaseModel):
    id: str = Field(default_factory=uuid7str)
    name: str
    url: str  # Git remote URL
    local_path: str
    default_branch: str = "main"
    last_synced: datetime | None = None
    is_cloned: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RepositoryCreate(BaseModel):
    """Request body for adding a repository."""
    url: str
    name: str | None = None  # Derived from URL if not provided
    default_branch: str = "main"
```

```python
# voyager/models/events.py

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class WebSocketEvent(BaseModel):
    """Base WebSocket event structure."""
    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict[str, Any] = Field(default_factory=dict)


class ProgressEventData(BaseModel):
    """Progress event payload mapped from NoeAgent ProgressEvent."""
    event_type: str  # step.start, step.complete, tool.start, etc.
    session_id: str
    sequence: int
    summary: str | None = None
    detail: str | None = None
    step_index: int | None = None
    step_desc: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    text: str | None = None
    error: str | None = None


class TaskCreatedEvent(WebSocketEvent):
    type: str = "task.created"
    data: dict  # Contains task_id, title, etc.


class TaskCompletedEvent(WebSocketEvent):
    type: str = "task.completed"
    data: dict  # Contains task_id, final_answer, etc.
```

### 2.2 Configuration Model

```python
# voyager/config.py

from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
from noesium.noeagent.config import NoeConfig, NoeMode


class VoyagerConfig(BaseModel):
    """Voyager-specific configuration."""
    
    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    
    # Paths
    data_root: Path = Field(default_factory=lambda: Path.home() / ".voyager")
    workspace_root: Path | None = None  # Derived from data_root if None
    
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
    
    def __post_init__(self):
        if self.workspace_root is None:
            self.workspace_root = self.data_root / "workspace"
    
    def get_noe_config(self, working_directory: str | None = None) -> NoeConfig:
        """Create NoeConfig for NoeAgent instances."""
        return NoeConfig(
            mode=NoeMode.AGENT,
            llm_provider=self.llm_provider,
            model_name=self.llm_model,
            max_iterations=self.max_iterations,
            reflection_interval=self.reflection_interval,
            working_directory=working_directory,
            enabled_toolkits=[
                "bash",
                "file_edit",
                "python_executor",
                "document",
                "github",
            ],
            permissions=[
                "fs:read",
                "fs:write",
                "shell:execute",
                "net:outbound",
            ],
        )
    
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
        return cls()
```

---

## 3. Backend Services

### 3.1 State Manager

File-based persistence layer using JSON for structured data and JSONL for event streams.

```python
# voyager/services/state_manager.py

import aiofiles
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from voyager.models.task import Task, TaskStatus
from voyager.models.repository import Repository
from voyager.models.events import ProgressEventData


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
        for path in sorted(
            self.tasks_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            task = await self.get_task(path.stem)
            if task is None:
                continue
            if status and task.status != status:
                continue
            if repository_id and task.repository_id != repository_id:
                continue
            tasks.append(task)
        return tasks[offset:offset + limit]
    
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
    
    async def append_event(
        self,
        task_id: str,
        event: ProgressEventData,
    ) -> None:
        """Append event to task's event log (JSONL format)."""
        path = self.tasks_dir / f"{task_id}-events.jsonl"
        async with aiofiles.open(path, "a") as f:
            await f.write(event.model_dump_json() + "\n")
    
    async def get_events(
        self,
        task_id: str,
        limit: int = 100,
    ) -> list[ProgressEventData]:
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
```

### 3.2 Git Client

GitPython-based repository operations.

```python
# voyager/services/git_client.py

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import git
from git import Repo, GitCommandError
from voyager.models.repository import Repository


class GitClient:
    """Git operations wrapper using GitPython."""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.workspace_root.mkdir(parents=True, exist_ok=True)
    
    def _run_async(self, func, *args, **kwargs):
        """Run synchronous git operations in thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def clone(
        self,
        url: str,
        name: str,
        branch: str = "main",
    ) -> Path:
        """Clone repository to workspace."""
        repo_path = self.workspace_root / name
        
        if repo_path.exists():
            raise ValueError(f"Repository already exists at {repo_path}")
        
        def _clone():
            return Repo.clone_from(
                url,
                str(repo_path),
                branch=branch,
            )
        
        await self._run_async(_clone)
        return repo_path
    
    async def pull(self, repo_path: Path) -> None:
        """Pull latest changes from remote."""
        def _pull():
            repo = Repo(str(repo_path))
            origin = repo.remotes.origin
            origin.pull()
        
        await self._run_async(_pull)
    
    async def create_branch(
        self,
        repo_path: Path,
        branch_name: str,
        base: str = "main",
    ) -> None:
        """Create and checkout new branch."""
        def _create_branch():
            repo = Repo(str(repo_path))
            # Fetch latest
            repo.remotes.origin.fetch()
            # Create branch from base
            base_ref = repo.refs[base] if base in repo.refs else repo.commit(base)
            repo.git.checkout(base_ref, b=branch_name)
        
        await self._run_async(_create_branch)
    
    async def commit(
        self,
        repo_path: Path,
        message: str,
        add_all: bool = True,
    ) -> str:
        """Stage changes and create commit. Returns commit SHA."""
        def _commit():
            repo = Repo(str(repo_path))
            
            if add_all:
                repo.git.add("-A")
            
            if repo.is_dirty(untracked_files=True):
                repo.index.commit(message)
            
            return repo.head.commit.hexsha
        
        return await self._run_async(_commit)
    
    async def push(
        self,
        repo_path: Path,
        branch: str,
        set_upstream: bool = True,
    ) -> None:
        """Push branch to remote."""
        def _push():
            repo = Repo(str(repo_path))
            if set_upstream:
                repo.git.push("-u", "origin", branch)
            else:
                repo.git.push("origin", branch)
        
        await self._run_async(_push)
    
    async def get_diff(
        self,
        repo_path: Path,
        base: str = "HEAD~1",
    ) -> str:
        """Get diff of changes."""
        def _diff():
            repo = Repo(str(repo_path))
            return repo.git.diff(base)
        
        return await self._run_async(_diff)
    
    async def get_status(self, repo_path: Path) -> dict:
        """Get repository status."""
        def _status():
            repo = Repo(str(repo_path))
            return {
                "branch": repo.active_branch.name if not repo.head.is_detached else "DETACHED",
                "is_dirty": repo.is_dirty(untracked_files=True),
                "untracked_files": repo.untracked_files,
                "changed_files": [item.a_path for item in repo.index.diff(None)],
            }
        
        return await self._run_async(_status)
    
    async def list_branches(self, repo_path: Path) -> list[str]:
        """List all branches."""
        def _list():
            repo = Repo(str(repo_path))
            return [b.name for b in repo.branches]
        
        return await self._run_async(_list)
    
    async def get_current_branch(self, repo_path: Path) -> str:
        """Get current branch name."""
        def _get():
            repo = Repo(str(repo_path))
            return repo.active_branch.name
        
        return await self._run_async(_get)
    
    async def checkout(self, repo_path: Path, branch: str) -> None:
        """Checkout existing branch."""
        def _checkout():
            repo = Repo(str(repo_path))
            repo.git.checkout(branch)
        
        await self._run_async(_checkout)
    
    async def get_file_content(
        self,
        repo_path: Path,
        file_path: str,
        revision: str = "HEAD",
    ) -> str:
        """Get file content at specific revision."""
        def _get():
            repo = Repo(str(repo_path))
            return repo.git.show(f"{revision}:{file_path}")
        
        return await self._run_async(_get)
    
    async def list_files(
        self,
        repo_path: Path,
        path_prefix: str = "",
    ) -> list[dict]:
        """List files in repository."""
        full_path = repo_path / path_prefix if path_prefix else repo_path
        
        if not full_path.exists():
            return []
        
        items = []
        for item in full_path.iterdir():
            if item.name.startswith("."):
                continue
            
            rel_path = str(item.relative_to(repo_path))
            
            if item.is_file():
                items.append({
                    "name": item.name,
                    "path": rel_path,
                    "type": "file",
                    "size": item.stat().st_size,
                })
            elif item.is_dir():
                items.append({
                    "name": item.name,
                    "path": rel_path,
                    "type": "directory",
                })
        
        return sorted(items, key=lambda x: (x["type"] == "file", x["name"]))
```

### 3.3 Session Manager

Manages NoeAgent instances per repository.

```python
# voyager/services/session_manager.py

import asyncio
from pathlib import Path
from typing import Optional
from noesium.noeagent import NoeAgent
from noesium.noeagent.config import NoeConfig, NoeMode
from voyager.config import VoyagerConfig
from voyager.models.repository import Repository
from voyager.services.state_manager import StateManager


class SessionManager:
    """Manages NoeAgent instances for repositories."""
    
    def __init__(
        self,
        state_manager: StateManager,
        config: VoyagerConfig,
    ):
        self._state = state_manager
        self._config = config
        self._agents: dict[str, NoeAgent] = {}
        self._lock = asyncio.Lock()
    
    async def get_agent(
        self,
        repository_id: str | None = None,
    ) -> NoeAgent:
        """Get or create NoeAgent for repository context."""
        async with self._lock:
            # If no repository, use default agent
            if repository_id is None:
                return await self._create_default_agent()
            
            # Check cache
            if repository_id in self._agents:
                return self._agents[repository_id]
            
            # Get repository info
            repo = await self._state.get_repository(repository_id)
            if repo is None:
                raise ValueError(f"Repository not found: {repository_id}")
            
            # Create agent with repo context
            agent = await self._create_agent_for_repo(repo)
            self._agents[repository_id] = agent
            return agent
    
    async def _create_default_agent(self) -> NoeAgent:
        """Create default agent without repository context."""
        noe_config = self._config.get_noe_config()
        agent = NoeAgent(noe_config)
        await agent.initialize()
        return agent
    
    async def _create_agent_for_repo(self, repo: Repository) -> NoeAgent:
        """Create agent configured for specific repository."""
        noe_config = self._config.get_noe_config(
            working_directory=repo.local_path
        )
        agent = NoeAgent(noe_config)
        await agent.initialize()
        return agent
    
    async def remove_agent(self, repository_id: str) -> None:
        """Remove agent from cache."""
        async with self._lock:
            if repository_id in self._agents:
                # Agent cleanup if needed
                del self._agents[repository_id]
    
    async def cleanup(self) -> None:
        """Cleanup all agent instances."""
        async with self._lock:
            for repo_id, agent in list(self._agents.items()):
                # NoeAgent doesn't have explicit cleanup yet
                pass
            self._agents.clear()
    
    def get_active_sessions(self) -> list[str]:
        """List active repository sessions."""
        return list(self._agents.keys())
```

### 3.4 Task Orchestrator

Bridges WebSocket to NoeAgent execution.

```python
# voyager/services/task_orchestrator.py

import asyncio
from datetime import datetime
from typing import Any, Optional
import socketio

from noesium.noeagent.progress import ProgressEvent, ProgressEventType
from voyager.config import VoyagerConfig
from voyager.models.task import Task, TaskStatus, TaskStep, CodeChange
from voyager.models.events import ProgressEventData
from voyager.services.state_manager import StateManager
from voyager.services.session_manager import SessionManager
from voyager.services.git_client import GitClient


class TaskOrchestrator:
    """Orchestrates task lifecycle and NoeAgent integration."""
    
    def __init__(
        self,
        state_manager: StateManager,
        session_manager: SessionManager,
        git_client: GitClient,
        config: VoyagerConfig,
    ):
        self._state = state_manager
        self._sessions = session_manager
        self._git = git_client
        self._config = config
        
        # Track running tasks
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
    
    async def create_task(
        self,
        title: str | None,
        description: str,
        repository_id: str | None = None,
        branch: str | None = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            title=title or description[:100],
            description=description,
            repository_id=repository_id,
            branch=branch,
            status=TaskStatus.CREATED,
        )
        await self._state.save_task(task)
        return task
    
    async def start_task(
        self,
        task_id: str,
        sio: socketio.AsyncServer,
        sid: str,
    ) -> None:
        """Start task execution with WebSocket streaming."""
        task = await self._state.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        
        # Update status
        task.status = TaskStatus.PLANNING
        task.updated_at = datetime.utcnow()
        await self._state.save_task(task)
        
        # Create cancel event
        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event
        
        # Start execution in background
        async def run():
            try:
                await self._execute_task(task, sio, sid, cancel_event)
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.updated_at = datetime.utcnow()
                await self._state.save_task(task)
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.updated_at = datetime.utcnow()
                await self._state.save_task(task)
                await self._emit_error(sio, sid, task_id, str(e))
            finally:
                self._cancel_events.pop(task_id, None)
        
        self._running_tasks[task_id] = asyncio.create_task(run())
    
    async def _execute_task(
        self,
        task: Task,
        sio: socketio.AsyncServer,
        sid: str,
        cancel_event: asyncio.Event,
    ) -> None:
        """Execute task with NoeAgent, streaming progress."""
        
        # Emit task started
        await sio.emit("task.started", {
            "task_id": task.task_id,
            "status": "planning",
        }, room=sid)
        
        # Get NoeAgent instance
        agent = await self._sessions.get_agent(task.repository_id)
        
        # Build context
        context = await self._build_context(task)
        
        # Stream progress events
        async for event in agent.astream_progress(task.description, context):
            # Check for cancellation
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            
            # Store event
            progress_event = self._map_progress_event(event)
            await self._state.append_event(task.task_id, progress_event)
            
            # Update task state based on event
            await self._update_task_from_event(task, event)
            
            # Emit to WebSocket
            await sio.emit("progress", {
                "task_id": task.task_id,
                "event": event.model_dump(),
            }, room=sid)
        
        # Mark completed
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        await self._state.save_task(task)
        
        # Emit completion
        await sio.emit("task.completed", {
            "task_id": task.task_id,
            "final_answer": task.final_answer,
            "code_changes": [c.model_dump() for c in task.code_changes],
        }, room=sid)
    
    async def _build_context(self, task: Task) -> dict[str, Any]:
        """Build execution context for NoeAgent."""
        context = {}
        
        if task.repository_id:
            repo = await self._state.get_repository(task.repository_id)
            if repo:
                context["repository"] = {
                    "name": repo.name,
                    "path": str(repo.local_path),
                    "branch": task.branch or repo.default_branch,
                }
                
                # Get recent changes
                try:
                    status = await self._git.get_status(Path(repo.local_path))
                    context["git_status"] = status
                except Exception:
                    pass
        
        return context
    
    async def _update_task_from_event(
        self,
        task: Task,
        event: ProgressEvent,
    ) -> None:
        """Update task state from NoeAgent progress event."""
        if event.type == ProgressEventType.PLAN_CREATED:
            task.status = TaskStatus.EXECUTING
            if event.plan_snapshot:
                # Extract steps from plan
                steps_data = event.plan_snapshot.get("steps", [])
                task.steps = [TaskStep(**s) for s in steps_data]
        
        elif event.type == ProgressEventType.STEP_START:
            if event.step_index is not None:
                task.current_step_index = event.step_index
                if event.step_index < len(task.steps):
                    task.steps[event.step_index].status = "in_progress"
                    task.steps[event.step_index].started_at = datetime.utcnow()
        
        elif event.type == ProgressEventType.STEP_COMPLETE:
            if event.step_index is not None and event.step_index < len(task.steps):
                task.steps[event.step_index].status = "completed"
                task.steps[event.step_index].completed_at = datetime.utcnow()
                if event.summary:
                    task.steps[event.step_index].result = event.summary
        
        elif event.type == ProgressEventType.REFLECTION:
            task.status = TaskStatus.REFLECTING
            if event.text:
                task.reasoning_trace.append({
                    "type": "reflection",
                    "text": event.text,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        
        elif event.type == ProgressEventType.FINAL_ANSWER:
            if event.text:
                task.final_answer = event.text
        
        elif event.type == ProgressEventType.ERROR:
            task.error_message = event.error or event.summary
        
        elif event.type == ProgressEventType.TOOL_END:
            if event.tool_name:
                task.tool_invocations.append({
                    "tool": event.tool_name,
                    "args": event.tool_args,
                    "result": event.tool_result[:500] if event.tool_result else None,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        
        task.updated_at = datetime.utcnow()
        await self._state.save_task(task)
    
    def _map_progress_event(self, event: ProgressEvent) -> ProgressEventData:
        """Map NoeAgent ProgressEvent to our event model."""
        return ProgressEventData(
            event_type=event.type.value,
            session_id=event.session_id,
            sequence=event.sequence,
            summary=event.summary,
            detail=event.detail,
            step_index=event.step_index,
            step_desc=event.step_desc,
            tool_name=event.tool_name,
            tool_args=event.tool_args,
            tool_result=event.tool_result[:1000] if event.tool_result else None,
            text=event.text,
            error=event.error,
        )
    
    async def _emit_error(
        self,
        sio: socketio.AsyncServer,
        sid: str,
        task_id: str,
        error: str,
    ) -> None:
        """Emit error event."""
        await sio.emit("task.error", {
            "task_id": task_id,
            "error": error,
        }, room=sid)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel running task."""
        if task_id in self._cancel_events:
            self._cancel_events[task_id].set()
            return True
        return False
    
    def is_task_running(self, task_id: str) -> bool:
        """Check if task is currently running."""
        return task_id in self._running_tasks
```

---

## 4. REST API Endpoints

### 4.1 Repository Endpoints

```python
# voyager/api/repositories.py

from pathlib import Path
from fastapi import APIRouter, HTTPException
from voyager.models.repository import Repository, RepositoryCreate
from voyager.services.state_manager import StateManager
from voyager.services.git_client import GitClient

router = APIRouter(prefix="/api/repositories", tags=["repositories"])

# Dependencies (injected via app state)
state_manager: StateManager = None
git_client: GitClient = None


@router.get("", response_model=list[Repository])
async def list_repositories():
    """List all registered repositories."""
    return await state_manager.list_repositories()


@router.post("", response_model=Repository)
async def add_repository(data: RepositoryCreate):
    """Add a new repository by cloning from URL."""
    # Derive name from URL if not provided
    name = data.name or data.url.split("/")[-1].replace(".git", "")
    
    # Check if already exists
    repos = await state_manager.list_repositories()
    if any(r.url == data.url for r in repos):
        raise HTTPException(400, "Repository URL already registered")
    
    # Clone repository
    try:
        local_path = await git_client.clone(data.url, name, data.default_branch)
    except Exception as e:
        raise HTTPException(400, f"Failed to clone repository: {e}")
    
    # Create repository record
    repo = Repository(
        name=name,
        url=data.url,
        local_path=str(local_path),
        default_branch=data.default_branch,
        is_cloned=True,
    )
    await state_manager.save_repository(repo)
    
    return repo


@router.get("/{repo_id}", response_model=Repository)
async def get_repository(repo_id: str):
    """Get repository details."""
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    return repo


@router.delete("/{repo_id}")
async def delete_repository(repo_id: str):
    """Remove repository from registry (does not delete files)."""
    deleted = await state_manager.delete_repository(repo_id)
    if not deleted:
        raise HTTPException(404, "Repository not found")
    return {"deleted": True}


@router.post("/{repo_id}/sync")
async def sync_repository(repo_id: str):
    """Pull latest changes from remote."""
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    
    try:
        await git_client.pull(Path(repo.local_path))
        return {"synced": True}
    except Exception as e:
        raise HTTPException(400, f"Failed to sync: {e}")


@router.get("/{repo_id}/files")
async def list_files(repo_id: str, path: str = ""):
    """List files in repository."""
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    
    files = await git_client.list_files(Path(repo.local_path), path)
    return {"files": files}


@router.get("/{repo_id}/files/{file_path:path}")
async def get_file_content(repo_id: str, file_path: str, revision: str = "HEAD"):
    """Get file content."""
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    
    try:
        content = await git_client.get_file_content(
            Path(repo.local_path), file_path, revision
        )
        return {"path": file_path, "content": content}
    except Exception as e:
        raise HTTPException(400, f"Failed to read file: {e}")


@router.get("/{repo_id}/branches")
async def list_branches(repo_id: str):
    """List all branches."""
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    
    branches = await git_client.list_branches(Path(repo.local_path))
    return {"branches": branches}
```

### 4.2 Task Endpoints

```python
# voyager/api/tasks.py

from fastapi import APIRouter, HTTPException, Query
from voyager.models.task import Task, TaskStatus, TaskCreate, TaskUpdate
from voyager.services.state_manager import StateManager
from voyager.services.task_orchestrator import TaskOrchestrator

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Dependencies
state_manager: StateManager = None
task_orchestrator: TaskOrchestrator = None


@router.get("", response_model=list[Task])
async def list_tasks(
    status: TaskStatus | None = Query(None),
    repository_id: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List tasks with optional filtering."""
    return await state_manager.list_tasks(
        status=status,
        repository_id=repository_id,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=Task)
async def create_task(data: TaskCreate):
    """Create a new task."""
    return await task_orchestrator.create_task(
        title=data.title,
        description=data.description,
        repository_id=data.repository_id,
        branch=data.branch,
    )


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """Get task details."""
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    if task_orchestrator.is_task_running(task_id):
        raise HTTPException(400, "Cannot delete running task")
    
    deleted = await state_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(404, "Task not found")
    return {"deleted": True}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel running task."""
    cancelled = await task_orchestrator.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(400, "Task is not running")
    return {"cancelled": True}


@router.get("/{task_id}/events")
async def get_task_events(task_id: str, limit: int = Query(100)):
    """Get task event log."""
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    
    events = await state_manager.get_events(task_id, limit)
    return {"events": [e.model_dump() for e in events]}


@router.get("/{task_id}/changes")
async def get_task_changes(task_id: str):
    """Get code changes from task."""
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    
    return {"changes": [c.model_dump() for c in task.code_changes]}


@router.get("/{task_id}/artifacts")
async def get_task_artifacts(task_id: str):
    """Get artifacts from task."""
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    
    return {"artifacts": [a.model_dump() for a in task.artifacts]}
```

---

## 5. WebSocket Integration

### 5.1 Socket.IO Handlers

```python
# voyager/api/websocket.py

import socketio
from voyager.services.task_orchestrator import TaskOrchestrator

# Socket.IO server instance
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Dependencies
task_orchestrator: TaskOrchestrator = None


@sio.event
async def connect(sid, environ):
    """Client connected."""
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    """Client disconnected."""
    print(f"Client disconnected: {sid}")


@sio.event
async def task_start(sid, data):
    """Start task execution."""
    task_id = data.get("task_id")
    if not task_id:
        await sio.emit("error", {"message": "task_id required"}, room=sid)
        return
    
    try:
        await task_orchestrator.start_task(task_id, sio, sid)
    except Exception as e:
        await sio.emit("error", {"message": str(e)}, room=sid)


@sio.event
async def task_cancel(sid, data):
    """Cancel running task."""
    task_id = data.get("task_id")
    if not task_id:
        return
    
    cancelled = await task_orchestrator.cancel_task(task_id)
    await sio.emit("task.cancelled", {
        "task_id": task_id,
        "cancelled": cancelled,
    }, room=sid)
```

---

## 6. Main Application

```python
# voyager/main.py

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from voyager.config import VoyagerConfig
from voyager.services.state_manager import StateManager
from voyager.services.git_client import GitClient
from voyager.services.session_manager import SessionManager
from voyager.services.task_orchestrator import TaskOrchestrator
from voyager.api import repositories, tasks, websocket
from voyager.api.websocket import sio


# Global instances
config: VoyagerConfig = None
state_manager: StateManager = None
git_client: GitClient = None
session_manager: SessionManager = None
task_orchestrator: TaskOrchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global config, state_manager, git_client, session_manager, task_orchestrator
    
    # Initialize configuration
    config = VoyagerConfig.load()
    config.data_root.mkdir(parents=True, exist_ok=True)
    
    # Initialize services
    state_manager = StateManager(config.data_root)
    git_client = GitClient(config.workspace_root)
    session_manager = SessionManager(state_manager, config)
    task_orchestrator = TaskOrchestrator(
        state_manager, session_manager, git_client, config
    )
    
    # Inject dependencies into API modules
    repositories.state_manager = state_manager
    repositories.git_client = git_client
    tasks.state_manager = state_manager
    tasks.task_orchestrator = task_orchestrator
    websocket.task_orchestrator = task_orchestrator
    
    yield
    
    # Cleanup
    await session_manager.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Voyager",
    description="Personal coding assistant webserver",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Include routers
app.include_router(repositories.router)
app.include_router(tasks.router)

# Health check
@app.get("/api/health")
async def health():
    return {"status": "healthy"}

# Serve frontend static files (in production)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")


def main():
    """CLI entry point for `voyager serve`."""
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    
    uvicorn.run(
        "voyager.main:socket_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
```

---

## 7. Frontend Implementation

### 7.1 Project Setup

```json
// coder/frontend/package.json
{
  "name": "voyager-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.24.0",
    "socket.io-client": "^4.7.0",
    "@monaco-editor/react": "^4.6.0",
    "marked": "^12.0.0",
    "highlight.js": "^11.9.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.1.0"
  }
}
```

### 7.2 TypeScript Types

```typescript
// coder/frontend/src/types/index.ts

export type TaskStatus = 
  | 'created' 
  | 'planning' 
  | 'executing' 
  | 'reflecting' 
  | 'completed' 
  | 'failed' 
  | 'cancelled';

export interface TaskStep {
  step_id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  result: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface CodeChange {
  file_path: string;
  change_type: 'created' | 'modified' | 'deleted';
  diff: string;
  lines_added: number;
  lines_removed: number;
}

export interface Task {
  task_id: string;
  title: string;
  description: string;
  status: TaskStatus;
  repository_id: string | null;
  branch: string | null;
  steps: TaskStep[];
  current_step_index: number;
  code_changes: CodeChange[];
  final_answer: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface Repository {
  id: string;
  name: string;
  url: string;
  local_path: string;
  default_branch: string;
  last_synced: string | null;
  is_cloned: boolean;
}

export interface ProgressEvent {
  task_id: string;
  event: {
    type: string;
    session_id: string;
    sequence: number;
    summary: string | null;
    detail: string | null;
    step_index: number | null;
    step_desc: string | null;
    tool_name: string | null;
    tool_args: Record<string, unknown> | null;
    tool_result: string | null;
    text: string | null;
    error: string | null;
  };
}

export interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
}
```

### 7.3 API Client

```typescript
// coder/frontend/src/services/api.ts

import type { Task, Repository, FileItem } from '../types';

const API_BASE = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  // Tasks
  listTasks: (params?: { status?: string; repository_id?: string }) => {
    const query = new URLSearchParams(params as Record<string, string>);
    return fetchJSON<{ tasks: Task[] }>(`${API_BASE}/tasks?${query}`);
  },
  
  getTask: (taskId: string) => 
    fetchJSON<Task>(`${API_BASE}/tasks/${taskId}`),
  
  createTask: (data: { description: string; repository_id?: string; branch?: string }) =>
    fetchJSON<Task>(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  
  deleteTask: (taskId: string) =>
    fetchJSON<{ deleted: boolean }>(`${API_BASE}/tasks/${taskId}`, {
      method: 'DELETE',
    }),
  
  cancelTask: (taskId: string) =>
    fetchJSON<{ cancelled: boolean }>(`${API_BASE}/tasks/${taskId}/cancel`, {
      method: 'POST',
    }),
  
  // Repositories
  listRepositories: () => 
    fetchJSON<Repository[]>(`${API_BASE}/repositories`),
  
  addRepository: (data: { url: string; name?: string }) =>
    fetchJSON<Repository>(`${API_BASE}/repositories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  
  getRepository: (repoId: string) =>
    fetchJSON<Repository>(`${API_BASE}/repositories/${repoId}`),
  
  deleteRepository: (repoId: string) =>
    fetchJSON<{ deleted: boolean }>(`${API_BASE}/repositories/${repoId}`, {
      method: 'DELETE',
    }),
  
  listFiles: (repoId: string, path?: string) => {
    const query = path ? `?path=${encodeURIComponent(path)}` : '';
    return fetchJSON<{ files: FileItem[] }>(`${API_BASE}/repositories/${repoId}/files${query}`);
  },
  
  getFileContent: (repoId: string, filePath: string) =>
    fetchJSON<{ path: string; content: string }>(
      `${API_BASE}/repositories/${repoId}/files/${encodeURIComponent(filePath)}`
    ),
};
```

### 7.4 Socket.IO Hook

```typescript
// coder/frontend/src/hooks/useSocket.ts

import { useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import type { ProgressEvent } from '../types';

const SOCKET_URL = '/';

interface UseSocketOptions {
  onProgress?: (event: ProgressEvent) => void;
  onTaskStarted?: (data: { task_id: string }) => void;
  onTaskCompleted?: (data: { task_id: string; final_answer: string }) => void;
  onTaskError?: (data: { task_id: string; error: string }) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function useSocket(options: UseSocketOptions = {}) {
  const socketRef = useRef<Socket | null>(null);
  
  useEffect(() => {
    socketRef.current = io(SOCKET_URL, {
      transports: ['websocket'],
    });
    
    const socket = socketRef.current;
    
    socket.on('connect', () => {
      console.log('Socket connected');
      options.onConnect?.();
    });
    
    socket.on('disconnect', () => {
      console.log('Socket disconnected');
      options.onDisconnect?.();
    });
    
    socket.on('progress', (event: ProgressEvent) => {
      options.onProgress?.(event);
    });
    
    socket.on('task.started', (data) => {
      options.onTaskStarted?.(data);
    });
    
    socket.on('task.completed', (data) => {
      options.onTaskCompleted?.(data);
    });
    
    socket.on('task.error', (data) => {
      options.onTaskError?.(data);
    });
    
    return () => {
      socket.disconnect();
    };
  }, []);
  
  const startTask = useCallback((taskId: string) => {
    socketRef.current?.emit('task_start', { task_id: taskId });
  }, []);
  
  const cancelTask = useCallback((taskId: string) => {
    socketRef.current?.emit('task_cancel', { task_id: taskId });
  }, []);
  
  return { startTask, cancelTask };
}
```

---

## 8. Implementation Checklist

### Phase 1: Backend Core
- [ ] Create `coder/backend/models/` with Task, Repository, Events
- [ ] Implement `StateManager` for JSON/JSONL persistence
- [ ] Implement `GitClient` with GitPython
- [ ] Create FastAPI app with basic REST endpoints
- [ ] Add unit tests for models and services

### Phase 2: NoeAgent Integration
- [ ] Implement `SessionManager` for NoeAgent lifecycle
- [ ] Implement `TaskOrchestrator` with progress streaming
- [ ] Integrate Socket.IO with FastAPI
- [ ] Wire WebSocket events to frontend
- [ ] Add integration tests

### Phase 3: Frontend
- [ ] Initialize Vite + React + TypeScript project
- [ ] Configure TailwindCSS
- [ ] Create layout components (Header, Sidebar)
- [ ] Implement TaskList and TaskCard components
- [ ] Implement TaskDetail view with progress timeline
- [ ] Add Monaco Editor for code viewing
- [ ] Integrate Socket.IO client
- [ ] Connect to backend API

### Phase 4: Polish
- [ ] Error handling and recovery
- [ ] Loading states and skeletons
- [ ] Dark/light theme support
- [ ] Keyboard shortcuts
- [ ] Documentation

---

## 9. Dependencies

### 9.1 Backend (coder-backend/pyproject.toml)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "voyager"
version = "0.1.0"
description = "Personal coding assistant webserver"
requires-python = ">=3.11"
dependencies = [
    # Core
    "pydantic>=2.0.0",
    "pydantic-settings>=2.12.0",
    "uuid7>=0.1.0",
    # Web framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    # WebSocket
    "python-socketio>=5.11.0",
    "python-engineio>=4.9.0",
    # Git operations
    "gitpython>=3.1.0",
    # Async file I/O
    "aiofiles>=24.1.0",
    # NoeAgent framework (depends on noesium)
    "noesium>=0.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=1.3.0",
    "httpx>=0.27.0",
]

[project.scripts]
voyager = "voyager.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/voyager"]
```

### 9.2 Frontend (coder-frontend/package.json)

```json
{
  "name": "voyager-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.24.0",
    "socket.io-client": "^4.7.0",
    "@monaco-editor/react": "^4.6.0",
    "marked": "^12.0.0",
    "highlight.js": "^11.9.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.1.0"
  }
}
```

## 10. Running the Projects

### 10.1 Backend

```bash
# Install dependencies
cd coder-backend
uv pip install -e .

# Run server
voyager serve

# Or with custom options
voyager serve --host 0.0.0.0 --port 8080
```

### 10.2 Frontend

```bash
# Install dependencies
cd coder-frontend
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### 10.3 Development Workflow

1. Start the backend server on port 8000
2. Start the frontend dev server on port 5173
3. Frontend proxies `/api` and `/socket.io` to backend
4. Open http://localhost:5173 in browser
