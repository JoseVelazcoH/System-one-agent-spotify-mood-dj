"""Runs PreparePlaylist as a background job, keeping one job per playlist id."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Protocol

from mood_dj.domain.models import PrepareProgress, PrepareState

logger = logging.getLogger(__name__)


class PreparableUseCase(Protocol):
    def run(self, playlist_id: str, access_token: str, on_progress=None) -> PrepareProgress: ...


class PrepareJobManager:
    """Starts and tracks background PreparePlaylist jobs, one per playlist id."""

    def __init__(self, use_case_factory: Callable[[], PreparableUseCase]) -> None:
        self._use_case_factory = use_case_factory
        self._lock = threading.Lock()
        self._progress: dict[str, PrepareProgress] = {}
        self._running: set[str] = set()

    def start(self, playlist_id: str, access_token: str) -> bool:
        """Start a job for `playlist_id` unless one is already running. Returns True if started."""
        with self._lock:
            if playlist_id in self._running:
                return False
            self._running.add(playlist_id)
            self._progress[playlist_id] = PrepareProgress(state=PrepareState.RUNNING)

        thread = threading.Thread(target=self._run, args=(playlist_id, access_token), daemon=True)
        thread.start()
        return True

    def status(self, playlist_id: str) -> PrepareProgress:
        with self._lock:
            return self._progress.get(playlist_id, PrepareProgress(state=PrepareState.IDLE))

    def _run(self, playlist_id: str, access_token: str) -> None:
        use_case = self._use_case_factory()

        def on_progress(progress: PrepareProgress) -> None:
            with self._lock:
                self._progress[playlist_id] = progress

        try:
            use_case.run(playlist_id, access_token, on_progress=on_progress)
        except Exception as error:  # noqa: BLE001 - reported via job status, not re-raised
            logger.warning("Prepare job failed for playlist %s", playlist_id, exc_info=True)
            with self._lock:
                self._progress[playlist_id] = PrepareProgress(state=PrepareState.ERROR, error=str(error))
        finally:
            with self._lock:
                self._running.discard(playlist_id)
