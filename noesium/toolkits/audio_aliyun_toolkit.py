"""
Audio processing toolkit using Aliyun NLS (Natural Language Service) for transcription.

.. deprecated::
    This module is deprecated. Use `noesium.toolkits.audio_toolkit.AudioToolkit` instead
    with `provider="aliyun"` configuration.

    Migration example:
        # Old:
        from noesium.toolkits.audio_aliyun_toolkit import AudioAliyunToolkit
        config = ToolkitConfig(
            name="audio_aliyun",
            config={
                "ALIYUN_ACCESS_KEY_ID": "...",
                "ALIYUN_ACCESS_KEY_SECRET": "...",
                "ALIYUN_NLS_APP_KEY": "...",
            }
        )
        toolkit = AudioAliyunToolkit(config)

        # New:
        from noesium.toolkits.audio_toolkit import AudioToolkit
        config = ToolkitConfig(
            name="audio",
            config={
                "provider": "aliyun",
                "ALIYUN_ACCESS_KEY_ID": "...",
                "ALIYUN_ACCESS_KEY_SECRET": "...",
                "ALIYUN_NLS_APP_KEY": "...",
            }
        )
        toolkit = AudioToolkit(config)

This module will be removed in a future version.
"""

import warnings

from noesium.core.toolify.config import ToolkitConfig
from noesium.core.toolify.registry import register_toolkit
from noesium.core.library_consts import TOOLKIT_AUDIO_ALIYUN
from noesium.toolkits.audio_toolkit import AudioToolkit as _AudioToolkit

warnings.warn(
    "AudioAliyunToolkit is deprecated. Use AudioToolkit with provider='aliyun' instead. "
    "See module docstring for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)


@register_toolkit(TOOLKIT_AUDIO_ALIYUN)
class AudioAliyunToolkit(_AudioToolkit):
    """
    Deprecated: Aliyun audio toolkit.

    .. deprecated::
        Use `AudioToolkit` with `provider="aliyun"` instead.

    This class exists for backward compatibility only.
    """

    def __init__(self, config: ToolkitConfig = None):
        # Ensure provider is set to aliyun
        if config:
            config.config["provider"] = "aliyun"
        super().__init__(config)
