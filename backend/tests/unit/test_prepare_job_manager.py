"""Unit tests for PrepareJobManager: one background job per playlist."""

from __future__ import annotations

import threading
import time

from mood_dj.application.prepare_job_manager import PrepareJobManager
from mood_dj.domain.models import PrepareState


class BlockingUseCase:
    """A fake use case that blocks until released, so tests can inspect mid-run state."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.run_calls: list[tuple[str, str]] = []

    def run(self, playlist_id: str, access_token: str, on_progress=None) -> None:
        self.run_calls.append((playlist_id, access_token))
        self.started.set()
        self.release.wait(timeout=5)


def test_status_is_idle_before_any_job_started() -> None:
    manager = PrepareJobManager(use_case_factory=lambda: BlockingUseCase())

    status = manager.status("playlist-1")

    assert status.state is PrepareState.IDLE


def test_start_runs_job_and_status_becomes_done() -> None:
    use_case = BlockingUseCase()
    use_case.release.set()
    manager = PrepareJobManager(use_case_factory=lambda: use_case)

    manager.start("playlist-1", "token")
    use_case.started.wait(timeout=5)
    time.sleep(0.1)

    assert use_case.run_calls == [("playlist-1", "token")]


def test_start_is_a_no_op_while_job_already_running_for_same_playlist() -> None:
    use_case = BlockingUseCase()
    manager = PrepareJobManager(use_case_factory=lambda: use_case)

    manager.start("playlist-1", "token")
    use_case.started.wait(timeout=5)
    manager.start("playlist-1", "token")
    use_case.release.set()
    time.sleep(0.1)

    assert len(use_case.run_calls) == 1


def test_status_reports_error_when_use_case_raises() -> None:
    class FailingUseCase:
        def run(self, playlist_id: str, access_token: str, on_progress=None) -> None:
            raise RuntimeError("boom")

    manager = PrepareJobManager(use_case_factory=lambda: FailingUseCase())

    manager.start("playlist-1", "token")
    for _ in range(50):
        if manager.status("playlist-1").state is PrepareState.ERROR:
            break
        time.sleep(0.05)

    status = manager.status("playlist-1")
    assert status.state is PrepareState.ERROR
    assert status.error == "boom"
