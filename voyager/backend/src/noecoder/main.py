"""NoeCoder main application - FastAPI with Socket.IO."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from noecoder.api import repositories, tasks
from noecoder.api.websocket import sio
from noecoder.config import NoeCoderConfig
from noecoder.services.git_client import GitClient
from noecoder.services.session_manager import SessionManager
from noecoder.services.state_manager import StateManager
from noecoder.services.task_orchestrator import TaskOrchestrator

# Global instances
config: NoeCoderConfig | None = None
state_manager: StateManager | None = None
git_client: GitClient | None = None
session_manager: SessionManager | None = None
task_orchestrator: TaskOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global config, state_manager, git_client, session_manager, task_orchestrator

    # Initialize configuration
    config = NoeCoderConfig.load()
    config.data_root.mkdir(parents=True, exist_ok=True)

    # Initialize services
    state_manager = StateManager(config.data_root)
    git_client = GitClient(config.workspace_root)
    session_manager = SessionManager(state_manager, config)
    task_orchestrator = TaskOrchestrator(state_manager, session_manager, git_client, config)

    # Inject dependencies into API modules
    repositories.state_manager = state_manager
    repositories.git_client = git_client
    tasks.state_manager = state_manager
    tasks.task_orchestrator = task_orchestrator
    from noecoder.api import websocket as ws_module

    ws_module.task_orchestrator = task_orchestrator

    yield

    # Cleanup
    await session_manager.cleanup()


# Create FastAPI app
app = FastAPI(
    title="NoeCoder",
    description="Personal coding assistant webserver powered by NoeAgent",
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

# Include routers
app.include_router(repositories.router)
app.include_router(tasks.router)


# Health check
@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


# Mount Socket.IO
socket_app = socketio.ASGIApp(sio, app)


def main() -> None:
    """CLI entry point for `noecoder`."""
    parser = argparse.ArgumentParser(description="NoeCoder - Personal coding assistant webserver")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args, _ = parser.parse_known_args()

    uvicorn.run(
        "noecoder.main:socket_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
