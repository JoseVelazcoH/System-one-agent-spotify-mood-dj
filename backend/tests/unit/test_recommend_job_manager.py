"""Unit tests for RecommendJobManager: one background job per session+playlist."""

from __future__ import annotations

import threading
import time

from mood_dj.application.recommend_job_manager import RecommendJobManager, RecommendJobState
from mood_dj.application.recommend_from_playlist import PlaylistRecommendation, RecommendPhase


class BlockingUseCase:
    """A fake use case that blocks until released, so tests can inspect mid-run state."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.run_calls: list[tuple[str, str, str]] = []

    def run(self, prompt: str, playlist_id: str, access_token: str, on_progress=None):
        self.run_calls.append((prompt, playlist_id, access_token))
        self.started.set()
        self.release.wait(timeout=5)
        if on_progress is not None:
            on_progress(RecommendPhase.BUILDING_PLAYLIST, 1, 1)
        return PlaylistRecommendation(
            strategy=None, signal_probabilities={}, stages=[], excluded_no_lyrics=0, excluded_instrumental=0
        )


def test_status_is_none_for_unknown_job() -> None:
    manager = RecommendJobManager(use_case_factory=lambda: BlockingUseCase())

    assert manager.status("nope") is None


def test_start_runs_job_and_status_becomes_done() -> None:
    use_case = BlockingUseCase()
    use_case.release.set()
    manager = RecommendJobManager(use_case_factory=lambda: use_case)

    job_id = manager.start("session-1", "playlist-1", "prompt", "token")
    for _ in range(50):
        status = manager.status(job_id)
        if status is not None and status.state is RecommendJobState.DONE:
            break
        time.sleep(0.02)

    status = manager.status(job_id)
    assert status is not None
    assert status.state is RecommendJobState.DONE
    assert status.result is not None
    assert use_case.run_calls == [("prompt", "playlist-1", "token")]


def test_start_returns_same_job_while_running_for_same_session_and_playlist() -> None:
    use_case = BlockingUseCase()
    manager = RecommendJobManager(use_case_factory=lambda: use_case)

    job_id = manager.start("session-1", "playlist-1", "prompt", "token")
    use_case.started.wait(timeout=5)
    second_job_id = manager.start("session-1", "playlist-1", "other prompt", "token")
    use_case.release.set()
    time.sleep(0.1)

    assert job_id == second_job_id
    assert len(use_case.run_calls) == 1


def test_different_sessions_get_independent_jobs_for_the_same_playlist() -> None:
    use_case = BlockingUseCase()
    manager = RecommendJobManager(use_case_factory=lambda: use_case)

    job_id_a = manager.start("session-a", "playlist-1", "prompt", "token")
    use_case.started.wait(timeout=5)
    use_case.release.set()
    time.sleep(0.1)

    use_case.started.clear()
    use_case.release.clear()
    job_id_b = manager.start("session-b", "playlist-1", "prompt", "token")

    assert job_id_a != job_id_b


def test_status_reports_error_when_use_case_raises() -> None:
    class FailingUseCase:
        def run(self, prompt, playlist_id, access_token, on_progress=None):
            raise RuntimeError("boom")

    manager = RecommendJobManager(use_case_factory=lambda: FailingUseCase())

    job_id = manager.start("session-1", "playlist-1", "prompt", "token")
    for _ in range(50):
        status = manager.status(job_id)
        if status is not None and status.state is RecommendJobState.ERROR:
            break
        time.sleep(0.02)

    status = manager.status(job_id)
    assert status is not None
    assert status.state is RecommendJobState.ERROR
    assert status.error == "boom"


def test_progress_callback_updates_phase_and_counts() -> None:
    manager = RecommendJobManager(use_case_factory=lambda: BlockingUseCase())
    use_case = manager._use_case_factory()
    manager._use_case_factory = lambda: use_case

    job_id = manager.start("session-1", "playlist-1", "prompt", "token")
    use_case.started.wait(timeout=5)
    use_case.release.set()
    for _ in range(50):
        status = manager.status(job_id)
        if status is not None and status.state is RecommendJobState.DONE:
            break
        time.sleep(0.02)

    status = manager.status(job_id)
    assert status is not None
    assert status.phase == RecommendPhase.BUILDING_PLAYLIST.value
    assert status.processed == 1
    assert status.total == 1
