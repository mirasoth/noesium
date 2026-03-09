"""Repository API endpoints."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from voyager.models.repository import Repository, RepositoryCreate
from voyager.services.git_client import GitClient
from voyager.services.state_manager import StateManager

router = APIRouter(prefix="/api/repositories", tags=["repositories"])

# Dependencies (injected via app state)
state_manager: StateManager | None = None
git_client: GitClient | None = None


@router.get("", response_model=list[Repository])
async def list_repositories() -> list[Repository]:
    """List all registered repositories."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    return await state_manager.list_repositories()


@router.post("", response_model=Repository)
async def add_repository(data: RepositoryCreate) -> Repository:
    """Add a new repository by cloning from URL."""
    if state_manager is None or git_client is None:
        raise HTTPException(500, "Server not initialized")

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
async def get_repository(repo_id: str) -> Repository:
    """Get repository details."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    return repo


@router.delete("/{repo_id}")
async def delete_repository(repo_id: str) -> dict[str, bool]:
    """Remove repository from registry (does not delete files)."""
    if state_manager is None:
        raise HTTPException(500, "Server not initialized")
    deleted = await state_manager.delete_repository(repo_id)
    if not deleted:
        raise HTTPException(404, "Repository not found")
    return {"deleted": True}


@router.post("/{repo_id}/sync")
async def sync_repository(repo_id: str) -> dict[str, bool]:
    """Pull latest changes from remote."""
    if state_manager is None or git_client is None:
        raise HTTPException(500, "Server not initialized")
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")

    try:
        await git_client.pull(Path(repo.local_path))
        return {"synced": True}
    except Exception as e:
        raise HTTPException(400, f"Failed to sync: {e}")


@router.get("/{repo_id}/files")
async def list_files(repo_id: str, path: str = "") -> dict[str, list[dict[str, Any]]]:
    """List files in repository."""
    if state_manager is None or git_client is None:
        raise HTTPException(500, "Server not initialized")
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")

    files = await git_client.list_files(Path(repo.local_path), path)
    return {"files": files}


@router.get("/{repo_id}/files/{file_path:path}")
async def get_file_content(
    repo_id: str, file_path: str, revision: str = "HEAD"
) -> dict[str, str]:
    """Get file content."""
    if state_manager is None or git_client is None:
        raise HTTPException(500, "Server not initialized")
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
async def list_branches(repo_id: str) -> dict[str, list[str]]:
    """List all branches."""
    if state_manager is None or git_client is None:
        raise HTTPException(500, "Server not initialized")
    repo = await state_manager.get_repository(repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")

    branches = await git_client.list_branches(Path(repo.local_path))
    return {"branches": branches}
