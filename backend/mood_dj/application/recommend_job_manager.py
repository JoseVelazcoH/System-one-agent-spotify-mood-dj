"""Runs RecommendFromPlaylist as a background job, one per session+playlist pair."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from mood_dj.application.recommend_from_playlist import PlaylistRecommendation, RecommendPhase

logger = logging.getLogger(__name__)

# Finished jobs are kept around for this long so a slow last poll can still see the
# result, then pruned so memory does not grow without bound.
FINISHED_JOB_TTL_S = 600


class RecommendJobState(str, Enum):
    """The lifecycle state of a recommendation job."""

    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class RecommendJobProgress:
    """Progress and outcome of a background recommendation job."""

    state: RecommendJobState = RecommendJobState.RUNNING
    phase: str = RecommendPhase.DETECTING_MOOD.value
    processed: int = 0
    total: int = 0
    result: PlaylistRecommendation | None = None
    error: str | None = None


class RecommendableUseCase(Protocol):
    def run(
        self, prompt: str, playlist_id: str, access_token: str, on_progress=None
    ) -> PlaylistRecommendation: ...


class RecommendJobManager:
    """Starts and tracks background recommend jobs, one running job per session+playlist."""

    def __init__(self, use_case_factory: Callable[[], RecommendableUseCase]) -> None:
        self._use_case_factory = use_case_factory
        self._lock = threading.Lock()
        self._jobs: dict[str, RecommendJobProgress] = {}
        self._finished_at: dict[str, float] = {}
        self._running_job_id: dict[tuple[str, str], str] = {}
        self._owner_by_job_id: dict[str, str] = {}

    def start(self, session_id: str, playlist_id: str, prompt: str, access_token: str) -> str:
        """Start a job for `(session_id, playlist_id)`, reusing one already running."""
        key = (session_id, playlist_id)
        with self._lock:
            self._prune_finished_locked()
            existing = self._running_job_id.get(key)
            if existing is not None:
                return existing

            job_id = uuid.uuid4().hex
            self._running_job_id[key] = job_id
            self._jobs[job_id] = RecommendJobProgress()
            self._owner_by_job_id[job_id] = session_id

        thread = threading.Thread(
            target=self._run, args=(key, job_id, prompt, playlist_id, access_token), daemon=True
        )
        thread.start()
        return job_id

    def status(self, job_id: str, session_id: str) -> RecommendJobProgress | None:
        """Return the job only to the session that started it; others see None (404)."""
        with self._lock:
            if self._owner_by_job_id.get(job_id) != session_id:
                return None
            return self._jobs.get(job_id)

    def _run(self, key: tuple[str, str], job_id: str, prompt: str, playlist_id: str, access_token: str) -> None:
        use_case = self._use_case_factory()

        def on_progress(phase: RecommendPhase, processed: int, total: int) -> None:
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.phase = phase.value
                    job.processed = processed
                    job.total = total

        try:
            result = use_case.run(prompt, playlist_id, access_token, on_progress=on_progress)
            with self._lock:
                job = self._jobs[job_id]
                job.state = RecommendJobState.DONE
                job.result = result
        except Exception as error:  # noqa: BLE001 - reported via job status, not re-raised
            logger.warning("Recommend job failed for playlist %s", playlist_id, exc_info=True)
            with self._lock:
                job = self._jobs[job_id]
                job.state = RecommendJobState.ERROR
                job.error = str(error)
        finally:
            with self._lock:
                self._running_job_id.pop(key, None)
                self._finished_at[job_id] = time.time()

    def _prune_finished_locked(self) -> None:
        now = time.time()
        expired = [jid for jid, finished_at in self._finished_at.items() if now - finished_at > FINISHED_JOB_TTL_S]
        for jid in expired:
            self._jobs.pop(jid, None)
            self._finished_at.pop(jid, None)
            self._owner_by_job_id.pop(jid, None)
