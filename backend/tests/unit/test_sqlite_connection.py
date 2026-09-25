"""Unit tests for the shared SQLite connection helper."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from mood_dj.adapters.sqlite_connection import open_connection
from mood_dj.adapters.sqlite_lyrics_repository import SqliteLyricsRepository
from mood_dj.domain.models import LyricsEntry, LyricsStatus


def test_open_connection_enables_wal_mode(tmp_path) -> None:
    db_path = str(tmp_path / "app.db")

    with open_connection(db_path) as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert mode == "wal"


def test_open_connection_reuses_one_connection_per_file(tmp_path) -> None:
    # Closing the last WAL connection forces a checkpoint, which made every
    # operation pay a disk sync; one long-lived connection per file avoids it.
    db_path = str(tmp_path / "app.db")

    with open_connection(db_path) as first:
        pass
    with open_connection(db_path) as second:
        second.execute("SELECT 1")

    assert first is second


def test_concurrent_reads_and_writes_do_not_lock(tmp_path) -> None:
    repository = SqliteLyricsRepository(str(tmp_path / "app.db"))

    def write_and_read(index: int) -> None:
        entry = LyricsEntry(
            track_id=f"t{index}", status=LyricsStatus.LYRICS, text="la la", fetched_at="now"
        )
        repository.save(entry)
        repository.get(f"t{index}")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_and_read, range(200)))
    elapsed = time.perf_counter() - started

    assert elapsed < 10
    assert all(repository.get(f"t{index}") is not None for index in range(200))
