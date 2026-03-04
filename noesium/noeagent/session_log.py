"""Session-specific JSONL logger for NoeAgent progress events (impl guide §5.8).

Captures every ``ProgressEvent`` -- including full tool args/results and
reflection text -- into a per-session ``.jsonl`` file for offline replay and
audit.  The file is created lazily on first write.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from uuid_extensions import uuid7str

from .progress import ProgressEvent

logger = logging.getLogger(__name__)


class SessionLogger:
    """Append-only JSONL writer that satisfies ``ProgressCallback``.

    When ``session_dir`` is provided the log is written as
    ``<session_dir>/session.jsonl`` (session-isolated layout).
    The legacy ``log_dir`` / ``session_id`` form is kept for backward
    compatibility but should not be used for new code.
    """

    def __init__(
        self,
        log_dir: str = ".noe_sessions",
        session_id: str | None = None,
        *,
        session_dir: str | None = None,
    ) -> None:
        self.session_id = session_id or uuid7str()
        if session_dir is not None:
            self._log_dir = Path(session_dir)
            self._log_path = self._log_dir / "session.jsonl"
        else:
            self._log_dir = Path(log_dir)
            self._log_path = self._log_dir / f"{self.session_id}.jsonl"
        self._lock = asyncio.Lock()
        self._initialised = False

    @property
    def log_path(self) -> Path:
        return self._log_path

    def _ensure_dir(self) -> None:
        if not self._initialised:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._initialised = True

    async def on_progress(self, event: ProgressEvent) -> None:
        """Write *event* as a single JSON line."""
        line = event.model_dump_json() + "\n"
        async with self._lock:
            self._ensure_dir()
            try:
                with open(self._log_path, "a", encoding="utf-8") as fh:
                    fh.write(line)
            except OSError as exc:
                logger.warning("SessionLogger write failed: %s", exc)
