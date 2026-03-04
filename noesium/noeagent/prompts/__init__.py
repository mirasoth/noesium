"""NoeAgent prompt loader using package resources."""

import importlib.resources
from typing import Any, Dict

from noesium.core.llm.prompt import PromptManager


class NoePromptManager:
    """Load and render prompts from noeagent.prompts package resources.

    Wraps the existing PromptManager to provide simple access to versioned
    markdown prompt files shipped with the noeagent package.
    """

    def __init__(self):
        """Initialize the prompt manager with format engine."""
        self._manager = PromptManager(default_engine="format")
        self._cache: Dict[str, str] = {}

    def render(self, name: str, **variables: Any) -> str:
        """Load and render a prompt from package resources.

        Args:
            name: Prompt name without .md extension (e.g., "agent_system")
            **variables: Template variables to substitute

        Returns:
            Rendered prompt string

        Raises:
            FileNotFoundError: If prompt file doesn't exist
            ValueError: If required variables are missing
        """
        # Load from cache or package resources
        if name not in self._cache:
            try:
                with importlib.resources.files("noesium.noeagent.prompts").joinpath(f"{name}.md").open("r") as f:
                    self._cache[name] = f.read()
            except Exception as exc:
                raise FileNotFoundError(f"Prompt '{name}' not found in noeagent.prompts package: {exc}") from exc

        # Use PromptManager to process
        template = self._manager.load_prompt(content=self._cache[name], name=name)
        messages = self._manager.render_prompt(template, variables)
        return messages[0].content if messages else ""

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()


# Global singleton instance
_prompt_manager: NoePromptManager | None = None


def get_prompt_manager() -> NoePromptManager:
    """Get the global NoePromptManager instance.

    Returns:
        NoePromptManager singleton instance
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = NoePromptManager()
    return _prompt_manager