from noesium.core.consts import set_noesium_home
from noesium.core.context import CognitiveContext
from noesium.core.memory.provider_manager import ProviderMemoryManager  # Import for Pydantic v2
from noesium.core.utils.logging import setup_logging

# Rebuild CognitiveContext model to resolve forward references (required for Pydantic v2)
CognitiveContext.model_rebuild()

# Enable colorful logging by default for noesium
setup_logging(level="INFO", enable_colors=True)

__all__ = ["set_noesium_home", "CognitiveContext"]
