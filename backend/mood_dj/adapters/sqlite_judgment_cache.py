"""JudgmentCache adapter backed by stdlib sqlite3, mirroring SqliteLyricsRepository."""

from __future__ import annotations

from pathlib import Path

from mood_dj.adapters.sqlite_connection import open_connection

_CREATE_TONE_TABLE = """
CREATE TABLE IF NOT EXISTS lyrics_tone (
    track_id TEXT NOT NULL,
    question_version TEXT NOT NULL,
    tone REAL NOT NULL,
    PRIMARY KEY (track_id, question_version)
)
"""

_CREATE_FIT_TABLE = """
CREATE TABLE IF NOT EXISTS lyrics_fit (
    track_id TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    question_version TEXT NOT NULL,
    fit REAL NOT NULL,
    PRIMARY KEY (track_id, prompt_hash, question_version)
)
"""


class SqliteJudgmentCache:
    """Stores Laya lyrics judgments (tone, fit) in a local SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(_CREATE_TONE_TABLE)
            connection.execute(_CREATE_FIT_TABLE)

    def _connect(self):
        return open_connection(self._db_path)

    def get_tone(self, track_id: str, question_version: str) -> float | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT tone FROM lyrics_tone WHERE track_id = ? AND question_version = ?",
                (track_id, question_version),
            ).fetchone()
        return row[0] if row is not None else None

    def save_tone(self, track_id: str, question_version: str, tone: float) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lyrics_tone (track_id, question_version, tone)
                VALUES (?, ?, ?)
                ON CONFLICT(track_id, question_version) DO UPDATE SET tone = excluded.tone
                """,
                (track_id, question_version, tone),
            )

    def get_fit(self, track_id: str, prompt_hash: str, question_version: str) -> float | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT fit FROM lyrics_fit
                WHERE track_id = ? AND prompt_hash = ? AND question_version = ?
                """,
                (track_id, prompt_hash, question_version),
            ).fetchone()
        return row[0] if row is not None else None

    def save_fit(self, track_id: str, prompt_hash: str, question_version: str, fit: float) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lyrics_fit (track_id, prompt_hash, question_version, fit)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(track_id, prompt_hash, question_version) DO UPDATE SET fit = excluded.fit
                """,
                (track_id, prompt_hash, question_version, fit),
            )
