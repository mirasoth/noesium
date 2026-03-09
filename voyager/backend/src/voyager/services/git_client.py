"""Git client using GitPython."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from git import Repo


class GitClient:
    """Git operations wrapper using GitPython."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _run_async(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run synchronous git operations in thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def clone(self, url: str, name: str, branch: str = "main") -> Path:
        """Clone repository to workspace."""
        repo_path = self.workspace_root / name

        if repo_path.exists():
            raise ValueError(f"Repository already exists at {repo_path}")

        def _clone() -> Repo:
            return Repo.clone_from(url, str(repo_path), branch=branch)

        await self._run_async(_clone)
        return repo_path

    async def pull(self, repo_path: Path) -> None:
        """Pull latest changes from remote."""

        def _pull() -> None:
            repo = Repo(str(repo_path))
            origin = repo.remotes.origin
            origin.pull()

        await self._run_async(_pull)

    async def create_branch(
        self, repo_path: Path, branch_name: str, base: str = "main"
    ) -> None:
        """Create and checkout new branch."""

        def _create_branch() -> None:
            repo = Repo(str(repo_path))
            # Fetch latest
            repo.remotes.origin.fetch()
            # Create branch from base
            base_ref = repo.refs[base] if base in repo.refs else repo.commit(base)
            repo.git.checkout(base_ref, b=branch_name)

        await self._run_async(_create_branch)

    async def commit(self, repo_path: Path, message: str, add_all: bool = True) -> str:
        """Stage changes and create commit. Returns commit SHA."""

        def _commit() -> str:
            repo = Repo(str(repo_path))

            if add_all:
                repo.git.add("-A")

            if repo.is_dirty(untracked_files=True):
                repo.index.commit(message)

            return repo.head.commit.hexsha

        return await self._run_async(_commit)

    async def push(
        self, repo_path: Path, branch: str, set_upstream: bool = True
    ) -> None:
        """Push branch to remote."""

        def _push() -> None:
            repo = Repo(str(repo_path))
            if set_upstream:
                repo.git.push("-u", "origin", branch)
            else:
                repo.git.push("origin", branch)

        await self._run_async(_push)

    async def get_diff(self, repo_path: Path, base: str = "HEAD~1") -> str:
        """Get diff of changes."""

        def _diff() -> str:
            repo = Repo(str(repo_path))
            return repo.git.diff(base)

        return await self._run_async(_diff)

    async def get_status(self, repo_path: Path) -> dict[str, Any]:
        """Get repository status."""

        def _status() -> dict[str, Any]:
            repo = Repo(str(repo_path))
            return {
                "branch": (
                    repo.active_branch.name if not repo.head.is_detached else "DETACHED"
                ),
                "is_dirty": repo.is_dirty(untracked_files=True),
                "untracked_files": repo.untracked_files,
                "changed_files": [item.a_path for item in repo.index.diff(None)],
            }

        return await self._run_async(_status)

    async def list_branches(self, repo_path: Path) -> list[str]:
        """List all branches."""

        def _list() -> list[str]:
            repo = Repo(str(repo_path))
            return [b.name for b in repo.branches]

        return await self._run_async(_list)

    async def get_current_branch(self, repo_path: Path) -> str:
        """Get current branch name."""

        def _get() -> str:
            repo = Repo(str(repo_path))
            return repo.active_branch.name

        return await self._run_async(_get)

    async def checkout(self, repo_path: Path, branch: str) -> None:
        """Checkout existing branch."""

        def _checkout() -> None:
            repo = Repo(str(repo_path))
            repo.git.checkout(branch)

        await self._run_async(_checkout)

    async def get_file_content(
        self, repo_path: Path, file_path: str, revision: str = "HEAD"
    ) -> str:
        """Get file content at specific revision."""

        def _get() -> str:
            repo = Repo(str(repo_path))
            return repo.git.show(f"{revision}:{file_path}")

        return await self._run_async(_get)

    async def list_files(
        self, repo_path: Path, path_prefix: str = ""
    ) -> list[dict[str, Any]]:
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
                items.append(
                    {
                        "name": item.name,
                        "path": rel_path,
                        "type": "file",
                        "size": item.stat().st_size,
                    }
                )
            elif item.is_dir():
                items.append(
                    {
                        "name": item.name,
                        "path": rel_path,
                        "type": "directory",
                    }
                )

        return sorted(items, key=lambda x: (x["type"] == "file", x["name"]))
