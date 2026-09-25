"""Unit tests for the CSV-to-Parquet dataset build script."""

from __future__ import annotations

import csv

import pyarrow.parquet as pq
import pytest

from scripts.build_dataset import build_dataset


def _write_csv(path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_dataset_writes_parquet_with_expected_schema(tmp_path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_csv(
        csv_path,
        [
            {
                "track_id": "abc123",
                "track_name": "Some Song",
                "artists": "Some Artist",
                "album_name": "Some Album",
                "energy": "0.5",
                "valence": "0.6",
                "tempo": "120.0",
                "danceability": "0.7",
                "acousticness": "0.2",
                "instrumentalness": "0.1",
            }
        ],
    )
    output_path = tmp_path / "out.parquet"

    build_dataset(csv_path, output_path)

    table = pq.read_table(output_path)
    assert table.num_rows == 1
    assert set(table.column_names) == {
        "id",
        "name",
        "artist",
        "album",
        "popularity",
        "energy",
        "valence",
        "tempo",
        "danceability",
        "acousticness",
        "instrumentalness",
    }
    assert table.column("id")[0].as_py() == "abc123"


def test_build_dataset_raises_on_missing_required_columns(tmp_path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_csv(csv_path, [{"track_id": "abc123", "track_name": "Some Song"}])
    output_path = tmp_path / "out.parquet"

    with pytest.raises(ValueError):
        build_dataset(csv_path, output_path)


def test_build_dataset_keeps_popularity_column_when_present(tmp_path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_csv(
        csv_path,
        [
            {
                "track_id": "abc123",
                "track_name": "Some Song",
                "artists": "Some Artist",
                "album_name": "Some Album",
                "popularity": "73",
                "energy": "0.5",
                "valence": "0.6",
                "tempo": "120.0",
                "danceability": "0.7",
                "acousticness": "0.2",
                "instrumentalness": "0.1",
            }
        ],
    )
    output_path = tmp_path / "out.parquet"

    build_dataset(csv_path, output_path)

    table = pq.read_table(output_path)
    assert "popularity" in table.column_names
    assert table.column("popularity")[0].as_py() == 73


def test_build_dataset_defaults_popularity_to_zero_when_absent(tmp_path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_csv(
        csv_path,
        [
            {
                "track_id": "abc123",
                "track_name": "Some Song",
                "artists": "Some Artist",
                "album_name": "Some Album",
                "energy": "0.5",
                "valence": "0.6",
                "tempo": "120.0",
                "danceability": "0.7",
                "acousticness": "0.2",
                "instrumentalness": "0.1",
            }
        ],
    )
    output_path = tmp_path / "out.parquet"

    build_dataset(csv_path, output_path)

    table = pq.read_table(output_path)
    assert "popularity" in table.column_names
    assert table.column("popularity")[0].as_py() == 0


def test_build_dataset_keeps_one_row_per_track_id(tmp_path) -> None:
    row = {
        "track_id": "abc123",
        "track_name": "Some Song",
        "artists": "Some Artist",
        "album_name": "Some Album",
        "energy": "0.5",
        "valence": "0.6",
        "tempo": "120.0",
        "danceability": "0.7",
        "acousticness": "0.2",
        "instrumentalness": "0.1",
    }
    csv_path = tmp_path / "input.csv"
    _write_csv(csv_path, [row, row, {**row, "track_id": "def456"}])
    output_path = tmp_path / "out.parquet"

    build_dataset(csv_path, output_path)

    ids = pq.read_table(output_path).column("id").to_pylist()
    assert sorted(ids) == ["abc123", "def456"]
