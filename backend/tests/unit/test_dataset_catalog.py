"""Unit tests for the DuckDB-backed dataset catalog adapter."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mood_dj.adapters.dataset_catalog import DatasetCatalog
from mood_dj.domain.models import MoodProfile


@pytest.fixture
def sample_parquet(tmp_path):
    table = pa.table(
        {
            "id": ["a", "b", "c", "d"],
            "name": ["Calm Song", "Energetic Song", "Sad Song", "Happy Song"],
            "artist": ["Artist A", "Artist B", "Artist C", "Artist D"],
            "album": ["Album A", "Album B", "Album C", "Album D"],
            "energy": [0.1, 0.9, 0.2, 0.8],
            "valence": [0.3, 0.7, 0.1, 0.9],
            "tempo": [70.0, 150.0, 60.0, 130.0],
            "danceability": [0.2, 0.8, 0.3, 0.7],
            "acousticness": [0.8, 0.1, 0.9, 0.2],
            "instrumentalness": [0.1, 0.0, 0.2, 0.0],
        }
    )
    path = tmp_path / "tracks.parquet"
    pq.write_table(table, path)
    return path


def test_find_candidates_returns_tracks_close_to_target(sample_parquet) -> None:
    catalog = DatasetCatalog(sample_parquet)
    profile = MoodProfile(energy=0.85, valence=0.8, tempo=140.0, instrumentalness=0.0)

    results = catalog.find_candidates(profile, limit=2)

    assert len(results) == 2
    assert results[0].id in {"b", "d"}


def test_find_candidates_respects_limit(sample_parquet) -> None:
    catalog = DatasetCatalog(sample_parquet)
    profile = MoodProfile(energy=0.5, valence=0.5, tempo=100.0, instrumentalness=0.1)

    results = catalog.find_candidates(profile, limit=1)

    assert len(results) == 1


@pytest.fixture
def duplicate_parquet(tmp_path):
    # Same song twice under different Spotify ids (album vs. single release), with
    # different-case name/artist, plus one distinct song.
    table = pa.table(
        {
            "id": ["a1", "a2", "b1"],
            "name": ["Calm Song", "calm song", "Other Song"],
            "artist": ["Artist A", "artist a", "Artist B"],
            "album": ["Album A", "Album A (Deluxe)", "Album B"],
            "energy": [0.1, 0.1, 0.2],
            "valence": [0.3, 0.3, 0.4],
            "tempo": [70.0, 70.0, 80.0],
            "danceability": [0.2, 0.2, 0.3],
            "acousticness": [0.8, 0.8, 0.7],
            "instrumentalness": [0.1, 0.1, 0.1],
            "popularity": [10, 90, 50],
        }
    )
    path = tmp_path / "tracks.parquet"
    pq.write_table(table, path)
    return path


def test_find_candidates_dedupes_by_name_and_artist_case_insensitive(duplicate_parquet) -> None:
    catalog = DatasetCatalog(duplicate_parquet)
    profile = MoodProfile(energy=0.1, valence=0.3, tempo=70.0, instrumentalness=0.1)

    results = catalog.find_candidates(profile, limit=10)

    names = [(track.name.lower(), track.artist.lower()) for track in results]
    assert len(names) == len(set(names))


def test_find_candidates_prefers_the_more_popular_duplicate(duplicate_parquet) -> None:
    catalog = DatasetCatalog(duplicate_parquet)
    profile = MoodProfile(energy=0.1, valence=0.3, tempo=70.0, instrumentalness=0.1)

    results = catalog.find_candidates(profile, limit=10)

    calm_song = next(t for t in results if t.name.lower() == "calm song")
    assert calm_song.id == "a2"


def test_find_candidates_works_without_popularity_column(sample_parquet) -> None:
    # sample_parquet has no popularity column at all; the catalog must not fail.
    catalog = DatasetCatalog(sample_parquet)
    profile = MoodProfile(energy=0.5, valence=0.5, tempo=100.0, instrumentalness=0.1)

    results = catalog.find_candidates(profile, limit=2)

    assert len(results) == 2
