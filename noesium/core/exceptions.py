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
