"""LyricsRepository adapter backed by stdlib sqlite3."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mood_dj.domain.models import LyricsEntry, LyricsStatus

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS lyrics (
    track_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    text TEXT,
    fetched_at TEXT NOT NULL
)
"""


class SqliteLyricsRepository:
    """Stores lyrics lookup results in a local SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def get(self, track_id: str) -> LyricsEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT track_id, status, text, fetched_at FROM lyrics WHERE track_id = ?",
                (track_id,),
            ).fetchone()
        if row is None:
            return None
        return LyricsEntry(
            track_id=row[0],
            status=LyricsStatus(row[1]),
            text=row[2],
            fetched_at=row[3],
        )

    def save(self, entry: LyricsEntry) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lyrics (track_id, status, text, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    status = excluded.status,
                    text = excluded.text,
                    fetched_at = excluded.fetched_at
                """,
                (entry.track_id, entry.status.value, entry.text, entry.fetched_at),
            )
