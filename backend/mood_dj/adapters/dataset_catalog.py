"""TrackCatalog adapter backed by a Parquet dataset, queried via DuckDB.

The Parquet file is expected to have columns: id, name, artist, album, energy,
valence, tempo, danceability, acousticness, instrumentalness. Build it from the
Kaggle Spotify tracks dataset with `scripts/build_dataset.py` (see the README).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from mood_dj.domain.models import MoodProfile, Track

# Tempo is on a much larger scale (BPM) than the other normalized features, so it is
# divided down before computing Euclidean distance, keeping every feature roughly
# comparable in the ranking query.
TEMPO_SCALE = 200.0

# A small nudge toward more popular tracks when candidates are otherwise close in
# distance. Popularity is 0-100 in the source dataset, so this keeps the bonus modest
# relative to typical feature distances (which are usually well under 1.0).
POPULARITY_BONUS_WEIGHT = 0.05

COLUMNS = [
    "id",
    "name",
    "artist",
    "album",
    "energy",
    "valence",
    "tempo",
    "danceability",
    "acousticness",
    "instrumentalness",
]


class DatasetCatalog:
    """Finds tracks in a Parquet dataset ranked by closeness to a target profile."""

    def __init__(self, parquet_path: str | Path) -> None:
        self._parquet_path = str(parquet_path)

    def find_candidates(self, profile: MoodProfile, limit: int) -> list[Track]:
        connection = duckdb.connect()
        popularity_expr = "popularity" if self._has_popularity_column(connection) else "0"

        query = f"""
            WITH scored AS (
                SELECT id, name, artist, album, energy, valence, tempo,
                       danceability, acousticness, instrumentalness,
                       (
                           POWER(energy - ?, 2)
                           + POWER(valence - ?, 2)
                           + POWER((tempo / ?) - (? / ?), 2)
                           + POWER(instrumentalness - ?, 2)
                       ) - ? * ({popularity_expr} / 100.0) AS distance,
                       ROW_NUMBER() OVER (
                           PARTITION BY lower(name), lower(artist)
                           ORDER BY {popularity_expr} DESC
                       ) AS duplicate_rank
                FROM read_parquet(?)
            )
            SELECT id, name, artist, album, energy, valence, tempo,
                   danceability, acousticness, instrumentalness
            FROM scored
            WHERE duplicate_rank = 1
            ORDER BY distance
            LIMIT ?
        """
        params = [
            profile.energy,
            profile.valence,
            TEMPO_SCALE,
            profile.tempo,
            TEMPO_SCALE,
            profile.instrumentalness,
            POPULARITY_BONUS_WEIGHT,
            self._parquet_path,
            limit,
        ]
        rows = connection.execute(query, params).fetchall()
        return [Track(**dict(zip(COLUMNS, row))) for row in rows]

    def _has_popularity_column(self, connection: duckdb.DuckDBPyConnection) -> bool:
        described = connection.execute(
            "SELECT * FROM read_parquet(?) LIMIT 0", [self._parquet_path]
        ).description
        return any(column[0] == "popularity" for column in described)
