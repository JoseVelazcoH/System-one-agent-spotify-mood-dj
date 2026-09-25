"""Unit tests for the SQLite-backed SpotifySessionStore."""

from __future__ import annotations

from mood_dj.adapters.sqlite_session_store import SqliteSessionStore
from mood_dj.domain.models import SpotifyTokens


def test_get_returns_none_for_unknown_session(tmp_path) -> None:
    store = SqliteSessionStore(str(tmp_path / "app.db"))

    assert store.get("unknown-session") is None


def test_save_then_get_returns_the_same_tokens(tmp_path) -> None:
    store = SqliteSessionStore(str(tmp_path / "app.db"))
    tokens = SpotifyTokens(access_token="access", refresh_token="refresh", expires_at=123.0)

    store.save("session-1", tokens)
    fetched = store.get("session-1")

    assert fetched == tokens


def test_save_overwrites_existing_tokens_for_same_session(tmp_path) -> None:
    store = SqliteSessionStore(str(tmp_path / "app.db"))
    store.save("session-1", SpotifyTokens(access_token="old", refresh_token="old-r", expires_at=1.0))

    store.save("session-1", SpotifyTokens(access_token="new", refresh_token="new-r", expires_at=2.0))

    fetched = store.get("session-1")
    assert fetched.access_token == "new"
    assert fetched.expires_at == 2.0


def test_delete_removes_the_session(tmp_path) -> None:
    store = SqliteSessionStore(str(tmp_path / "app.db"))
    store.save("session-1", SpotifyTokens(access_token="a", refresh_token="r", expires_at=1.0))

    store.delete("session-1")

    assert store.get("session-1") is None


def test_delete_is_safe_for_unknown_session(tmp_path) -> None:
    store = SqliteSessionStore(str(tmp_path / "app.db"))

    store.delete("does-not-exist")
