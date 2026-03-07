from noesium.core.consts import set_noesium_home
from noesium.core.utils.logging import setup_logging

# Enable colorful logging by default for noesium
setup_logging(level="INFO", enable_colors=True)

# Import autonomous module to make it available

__all__ = ["set_noesium_home", "autonomous"]
