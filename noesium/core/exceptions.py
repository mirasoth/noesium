"""Noesium framework exception hierarchy."""


class NoesiumError(Exception):
    """Base exception for all Noesium errors."""


# --- Event system ---


class EventError(NoesiumError):
    """Event system errors."""


class EventValidationError(EventError):
    """Event envelope validation failure."""


class EventStoreError(EventError):
    """Event store read/write failure."""


# --- Kernel execution ---


class KernelError(NoesiumError):
    """Kernel execution errors."""


class NodeExecutionError(KernelError):
    """Graph node execution failure."""


class CheckpointError(KernelError):
    """Checkpoint save/load failure."""


# --- Projection ---


class ProjectionError(NoesiumError):
    """Projection computation errors."""


class ProjectionVersionError(ProjectionError):
    """Projection version mismatch requiring rebuild."""


# --- Capability ---


class CapabilityError(NoesiumError):
    """Capability registry/resolution errors."""


class CapabilityNotFoundError(CapabilityError):
    """No matching capability found."""


# --- Memory ---


class MemoryError(NoesiumError):
    """Memory subsystem errors."""


class ProviderNotFoundError(MemoryError):
    """Requested provider_id is not registered."""


class ProviderReadOnlyError(MemoryError):
    """Write attempted on a read-only provider."""


class RecallError(MemoryError):
    """Recall query failed across all providers."""


# --- Tools ---


class ToolError(NoesiumError):
    """Base tool exception."""


class ToolNotFoundError(ToolError):
    """Tool not found in registry."""


class ToolExecutionError(ToolError):
    """Tool execution failed."""


class ToolTimeoutError(ToolError):
    """Tool execution timed out."""


class ToolPermissionError(ToolError):
    """Insufficient permissions for tool."""


class SkillNotFoundError(ToolError):
    """Skill not found in registry."""


# --- Noe ---


class Noer(NoesiumError):
    """Base Noe error."""


class PlanningError(Noer):
    """Task planning or revision failed."""


class ModeError(Noer):
    """Invalid mode or mode-specific constraint violation."""


class IterationLimitError(Noer):
    """Max iterations exceeded."""
