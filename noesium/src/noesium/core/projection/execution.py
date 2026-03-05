"""Execution projection tracking node lifecycles (RFC-1001 Section 8.1)."""

from __future__ import annotations

from typing import Any

from noesium.core.event.envelope import EventEnvelope

from .base import BaseProjection

ExecutionState = dict[str, Any]


class ExecutionProjection(BaseProjection[ExecutionState]):
    """Tracks node executions, task states, and retry counts from kernel events."""

    def initial_state(self) -> ExecutionState:
        return {
            "node_executions": {},
            "task_states": {},
            "total_nodes_entered": 0,
            "total_nodes_completed": 0,
        }

    def apply(self, state: ExecutionState, event: EventEnvelope) -> ExecutionState:
        et = event.event_type
        p = event.payload

        if et == "kernel.node.entered":
            node_id = p.get("node_id", "unknown")
            state["total_nodes_entered"] += 1
            entry = state["node_executions"].setdefault(node_id, {"entered": 0, "completed": 0, "total_ms": 0.0})
            entry["entered"] += 1

        elif et == "kernel.node.completed":
            node_id = p.get("node_id", "unknown")
            state["total_nodes_completed"] += 1
            entry = state["node_executions"].setdefault(node_id, {"entered": 0, "completed": 0, "total_ms": 0.0})
            entry["completed"] += 1
            entry["total_ms"] += p.get("duration_ms", 0.0)

        elif et == "task.requested":
            task_id = p.get("task_id", "unknown")
            state["task_states"][task_id] = "requested"

        elif et == "task.completed":
            task_id = p.get("task_id", "unknown")
            state["task_states"][task_id] = "completed" if not p.get("error") else "failed"

        return state
