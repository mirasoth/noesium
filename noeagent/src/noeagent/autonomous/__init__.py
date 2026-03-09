"""NoeAgent autonomous mode components (RFC-1005, RFC-1006, RFC-1007).

This module provides the autonomous execution layer for NoeAgent:
- Goal, GoalStatus: Goal model and lifecycle
- GoalEngine: Goal scheduling and persistence
- Goal events: GoalCreated, GoalUpdated, GoalCompleted, GoalFailed
- CognitiveLoop, CognitiveLoopMetrics: Continuous reasoning and execution loop
- AutonomousRunner, run_autonomous_mode: Entry point for autonomous mode
- Event system: AutonomousEvent, EventProcessor, EventQueue
- Trigger rules: Trigger, TriggerRule
- Event sources: TimerEventSource, FileSystemEventSource, WatchdogFileSystemEventSource
- Event replay: EventReplayer
- Decision schema: Decision, DecisionAction, *Decision (for Agent Kernel)
"""

from .cognitive_loop import CognitiveLoop, CognitiveLoopMetrics
from .decision_schema import (
    CreateGoalDecision,
    Decision,
    DecisionAction,
    FinishGoalDecision,
    GoalUpdateDecision,
    MemoryUpdateDecision,
    SubagentCallDecision,
    ToolCallDecision,
)
from .event_processor import EventProcessor
from .event_queue import EventQueue
from .event_replay import EventReplayer
from .event_sources import (
    WATCHDOG_AVAILABLE,
    FileSystemEventSource,
    TimerEventSource,
    WatchdogFileSystemEventSource,
    WebhookEventSource,
    get_filesystem_event_source,
)
from .event_system import AutonomousEvent
from .goal_engine import Goal, GoalEngine, GoalStatus
from .goal_events import GoalCompleted, GoalCreated, GoalFailed, GoalUpdated
from .runner import AutonomousRunner, run_autonomous_mode
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
    # Decision schema (Agent Kernel)
    "Decision",
    "DecisionAction",
    "CreateGoalDecision",
    "ToolCallDecision",
    "SubagentCallDecision",
    "MemoryUpdateDecision",
    "GoalUpdateDecision",
    "FinishGoalDecision",
    # Event System
    "AutonomousEvent",
    "EventProcessor",
    "EventQueue",
    "EventReplayer",
    "Trigger",
    "TriggerRule",
    # Event Sources
    "TimerEventSource",
    "FileSystemEventSource",
    "WatchdogFileSystemEventSource",
    "WebhookEventSource",
    "get_filesystem_event_source",
    "WATCHDOG_AVAILABLE",
    # Cognitive Loop & Runner
    "CognitiveLoop",
    "CognitiveLoopMetrics",
    "AutonomousRunner",
    "run_autonomous_mode",
]
