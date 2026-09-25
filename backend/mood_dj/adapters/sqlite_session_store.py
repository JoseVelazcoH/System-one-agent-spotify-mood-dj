"""SpotifySessionStore adapter backed by stdlib sqlite3."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mood_dj.domain.models import SpotifyTokens

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at REAL NOT NULL
)
"""


class SqliteSessionStore:
    """Stores Spotify OAuth tokens per app session id in a local SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, session_id: str, tokens: SpotifyTokens) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, access_token, refresh_token, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expires_at = excluded.expires_at
                """,
                (session_id, tokens.access_token, tokens.refresh_token, tokens.expires_at),
            )

    def get(self, session_id: str) -> SpotifyTokens | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT access_token, refresh_token, expires_at FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return SpotifyTokens(access_token=row[0], refresh_token=row[1], expires_at=row[2])

    def delete(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
