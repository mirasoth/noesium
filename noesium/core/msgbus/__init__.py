"""Generic event-watchdog framework based on bubus library."""

from bubus import BaseEvent, EventBus

from .base import BaseWatchdog, EventProcessor
from .bridge import EnvelopeBridge, EnvelopeEvent

__all__ = [
    "BaseEvent",
    "BaseWatchdog",
    "EnvelopeBridge",
    "EnvelopeEvent",
    "EventBus",
    "EventProcessor",
]
