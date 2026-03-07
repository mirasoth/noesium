"""NoeAgent autonomous mode components (RFC-1005).

This module provides the autonomous execution layer for NoeAgent:
- CognitiveLoop: Continuous reasoning and execution loop
- AutonomousRunner: Entry point for autonomous mode
"""

from .cognitive_loop import CognitiveLoop
from .runner import AutonomousRunner, run_autonomous_mode

__all__ = [
    "CognitiveLoop",
    "AutonomousRunner",
    "run_autonomous_mode",
]
