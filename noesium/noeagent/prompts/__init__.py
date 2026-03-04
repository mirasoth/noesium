"""NoeAgent prompt loader using package resources."""

import importlib.resources
from typing import Any, Dict

from noesium.core.llm.prompt import PromptLoader, PromptManager


class NoePromptManager:
    """Load and render prompts from noeagent.prompts package resources.

    Wraps the existing PromptManager to provide simple access to versioned
    markdown prompt files shipped with the noeagent package. Uses frontmatter
    for template_engine, required_variables, and optional_variables.
    """

    def __init__(self):
        """Initialize the prompt manager with format engine."""
        self._manager = PromptManager(default_engine="format")
        self._cache: Dict[str, str] = {}

    def render(self, name: str, **variables: Any) -> str:
        """Load and render a prompt from package resources.

        Parses YAML frontmatter so that only the body is sent to the LLM,
        template_engine (e.g. format) is applied, and required/optional
        variables are validated and defaulted.

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

        # Parse frontmatter and body so template_engine, required_variables, optional_variables apply
        template = PromptLoader.from_markdown_string(self._cache[name], name=name)
        try:
            messages = self._manager.render_prompt(template, variables)
        except ValueError as exc:
            msg = str(exc)
            if "required" in msg.lower() or "missing" in msg.lower():
                raise ValueError(f"Prompt '{name}' missing required variable(s): {msg}") from exc
            raise
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
