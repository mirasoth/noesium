"""NoeAgent autonomous mode components (RFC-1005, RFC-1006, RFC-1007).

This module provides the autonomous execution layer for NoeAgent:
- Goal, GoalStatus: Goal model and lifecycle
- GoalEngine: Goal scheduling and persistence
- Goal events: GoalCreated, GoalUpdated, GoalCompleted, GoalFailed
- CognitiveLoop: Continuous reasoning and execution loop
- AutonomousRunner, run_autonomous_mode: Entry point for autonomous mode
- Event system: AutonomousEvent, EventProcessor, EventQueue
- Trigger rules: Trigger, TriggerRule
- Event sources: TimerEventSource, FileSystemEventSource, WebhookEventSource
- Decision schema: Decision, DecisionAction, *Decision (for Agent Kernel)
"""

from .cognitive_loop import CognitiveLoop
from .decision_schema import (
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
from .event_sources import FileSystemEventSource, TimerEventSource, WebhookEventSource
from .event_system import AutonomousEvent
from .events import GoalCompleted, GoalCreated, GoalFailed, GoalUpdated
from .goal_engine import GoalEngine

# Import base modules first to avoid circular import (cognitive_loop imports Goal, GoalEngine)
from .models import Goal, GoalStatus
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
    "ToolCallDecision",
    "SubagentCallDecision",
    "MemoryUpdateDecision",
    "GoalUpdateDecision",
    "FinishGoalDecision",
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
    # Cognitive Loop & Runner
    "CognitiveLoop",
    "AutonomousRunner",
    "run_autonomous_mode",
]
