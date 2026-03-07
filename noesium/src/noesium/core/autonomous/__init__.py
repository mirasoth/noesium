"""Autonomous architecture components (RFCs 1005, 1006, 1007).

This module provides the core components for autonomous agent operation:
- Goal Engine: Manages goals and scheduling
- Event System: Reactive event processing
- Trigger Rules: Convert events to goals
"""

from .event_processor import EventProcessor
from .event_queue import EventQueue
from .event_sources import FileSystemEventSource, TimerEventSource, WebhookEventSource
from .event_system import AutonomousEvent
from .events import GoalCompleted, GoalCreated, GoalFailed, GoalUpdated
from .goal_engine import GoalEngine
from .models import Goal, GoalStatus
from .trigger import Trigger, TriggerRule

__all__ = [
    # Goal models
    "Goal",
    "GoalStatus",
    # Goal Engine
    "GoalEngine",
    # Goal events
    "GoalCreated",
    "GoalUpdated",
    "GoalCompleted",
    "GoalFailed",
    # Event System
    "AutonomousEvent",
    "EventProcessor",
    "EventQueue",
    "Trigger",
    "TriggerRule",
    # Event Sources
    "TimerEventSource",
    "FileSystemEventSource",
    "WebhookEventSource",
]
