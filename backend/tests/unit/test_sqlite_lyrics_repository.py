"""Unit tests for the SQLite-backed LyricsRepository."""

from __future__ import annotations

from mood_dj.adapters.sqlite_lyrics_repository import SqliteLyricsRepository
from mood_dj.domain.models import LyricsEntry, LyricsStatus


def test_get_returns_none_for_unknown_track(tmp_path) -> None:
    repo = SqliteLyricsRepository(str(tmp_path / "app.db"))

    assert repo.get("unknown-track") is None


def test_save_then_get_returns_the_same_entry(tmp_path) -> None:
    repo = SqliteLyricsRepository(str(tmp_path / "app.db"))
    entry = LyricsEntry(
        track_id="track-1",
        status=LyricsStatus.LYRICS,
        text="la la la",
        fetched_at="2026-09-25T00:00:00+00:00",
    )

    repo.save(entry)
    fetched = repo.get("track-1")

    assert fetched == entry


def test_save_overwrites_existing_entry_for_same_track(tmp_path) -> None:
    repo = SqliteLyricsRepository(str(tmp_path / "app.db"))
    repo.save(
        LyricsEntry(
            track_id="track-1",
            status=LyricsStatus.MISSING,
            text=None,
            fetched_at="2026-09-25T00:00:00+00:00",
        )
    )

    repo.save(
        LyricsEntry(
            track_id="track-1",
            status=LyricsStatus.LYRICS,
            text="found later",
            fetched_at="2026-09-26T00:00:00+00:00",
        )
    )

    fetched = repo.get("track-1")
    assert fetched.status is LyricsStatus.LYRICS
    assert fetched.text == "found later"


def test_creates_db_file_and_parent_directory(tmp_path) -> None:
    db_path = tmp_path / "nested" / "app.db"

    SqliteLyricsRepository(str(db_path))

    assert db_path.exists()


def test_instrumental_status_persists_without_text(tmp_path) -> None:
    repo = SqliteLyricsRepository(str(tmp_path / "app.db"))
    repo.save(
        LyricsEntry(
            track_id="instr-1",
            status=LyricsStatus.INSTRUMENTAL,
            text=None,
            fetched_at="2026-09-25T00:00:00+00:00",
        )
    )

    fetched = repo.get("instr-1")
    assert fetched.status is LyricsStatus.INSTRUMENTAL
    assert fetched.text is None
