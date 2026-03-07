"""Session Manager for NoeAgent instances."""

from __future__ import annotations

import asyncio

from voyager.config import VoyagerConfig
from voyager.models.repository import Repository
from voyager.services.state_manager import StateManager

from noeagent import NoeAgent
from noeagent.config import NoeConfig, NoeMode


class SessionManager:
    """Manages NoeAgent instances for repositories."""

    def __init__(self, state_manager: StateManager, config: VoyagerConfig):
        self._state = state_manager
        self._config = config
        self._agents: dict[str, NoeAgent] = {}
        self._lock = asyncio.Lock()

    async def get_agent(self, repository_id: str | None = None) -> NoeAgent:
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
        config_kwargs = self._config.get_noe_config()
        noe_config = NoeConfig(mode=NoeMode.AGENT, **config_kwargs)
        agent = NoeAgent(noe_config)
        await agent.initialize()
        return agent

    async def _create_agent_for_repo(self, repo: Repository) -> NoeAgent:
        """Create agent configured for specific repository."""
        config_kwargs = self._config.get_noe_config(working_directory=repo.local_path)
        noe_config = NoeConfig(mode=NoeMode.AGENT, **config_kwargs)
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
            self._agents.clear()

    def get_active_sessions(self) -> list[str]:
        """List active repository sessions."""
        return list(self._agents.keys())
