"""Unit tests for the SQLite-backed JudgmentCache."""

from __future__ import annotations

from mood_dj.adapters.sqlite_judgment_cache import SqliteJudgmentCache


def test_get_tone_returns_none_when_uncached(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))

    assert cache.get_tone("track-1", "v1") is None


def test_save_then_get_tone_returns_the_same_value(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))

    cache.save_tone("track-1", "v1", 0.75)

    assert cache.get_tone("track-1", "v1") == 0.75


def test_tone_is_scoped_by_question_version(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))
    cache.save_tone("track-1", "v1", 0.75)

    assert cache.get_tone("track-1", "v2") is None


def test_get_fit_returns_none_when_uncached(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))

    assert cache.get_fit("track-1", "hash-a", "v1") is None


def test_save_then_get_fit_returns_the_same_value(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))

    cache.save_fit("track-1", "hash-a", "v1", 0.42)

    assert cache.get_fit("track-1", "hash-a", "v1") == 0.42


def test_fit_is_scoped_by_prompt_hash(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))
    cache.save_fit("track-1", "hash-a", "v1", 0.42)

    assert cache.get_fit("track-1", "hash-b", "v1") is None


def test_save_overwrites_existing_tone(tmp_path) -> None:
    cache = SqliteJudgmentCache(str(tmp_path / "app.db"))
    cache.save_tone("track-1", "v1", 0.1)

    cache.save_tone("track-1", "v1", 0.9)

    assert cache.get_tone("track-1", "v1") == 0.9


def test_creates_db_file_and_parent_directory(tmp_path) -> None:
    db_path = tmp_path / "nested" / "app.db"

    SqliteJudgmentCache(str(db_path))

    assert db_path.exists()
