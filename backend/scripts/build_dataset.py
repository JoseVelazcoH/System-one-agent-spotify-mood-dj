"""Convert a Kaggle Spotify tracks CSV into the Parquet file the catalog reads.

With no arguments, the default public dataset is downloaded via kagglehub (no
credentials required for public datasets), so every run starts from the same source.

Usage:
    uv run scripts/build_dataset.py                  # download default dataset
    uv run scripts/build_dataset.py <input_csv> [output_parquet]

If output_parquet is omitted, it defaults to data/tracks.parquet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq

REQUIRED_COLUMNS = [
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

# Common Kaggle column name variants, mapped to the schema this project expects.
COLUMN_ALIASES = {
    "track_id": "id",
    "track_name": "name",
    "artists": "artist",
    "artist_name": "artist",
    "album_name": "album",
}

# Optional column: kept if present in the source CSV, defaulted to 0 otherwise so the
# catalog can always rank by popularity without special-casing older datasets.
OPTIONAL_COLUMNS_WITH_DEFAULTS = {"popularity": 0}

DEFAULT_OUTPUT = "data/tracks.parquet"
DEFAULT_KAGGLE_DATASET = "maharshipandya/-spotify-tracks-dataset"
DEFAULT_CSV_NAME = "dataset.csv"


def build_dataset(input_csv: Path, output_parquet: Path) -> None:
    table = pa_csv.read_csv(input_csv)
    renamed = {name: COLUMN_ALIASES.get(name, name) for name in table.column_names}
    table = table.rename_columns([renamed[name] for name in table.column_names])

    missing = [column for column in REQUIRED_COLUMNS if column not in table.column_names]
    if missing:
        raise ValueError(
            f"input CSV is missing required columns after aliasing: {missing}. "
            f"Available columns: {table.column_names}"
        )

    for column, default in OPTIONAL_COLUMNS_WITH_DEFAULTS.items():
        if column not in table.column_names:
            table = table.append_column(column, pa.array([default] * table.num_rows))

    output_columns = REQUIRED_COLUMNS + list(OPTIONAL_COLUMNS_WITH_DEFAULTS)
    selected = table.select(output_columns)
    selected = selected.set_column(
        selected.column_names.index("id"),
        "id",
        pc.cast(selected.column("id"), pa.string()),
    )

    selected = _keep_first_row_per_id(selected)

    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(selected, output_parquet)
    print(f"Wrote {selected.num_rows} tracks to {output_parquet}")


def _keep_first_row_per_id(table: pa.Table) -> pa.Table:
    # Kaggle datasets repeat a track once per genre; keep a single row per track id.
    indexed = table.append_column("_row", pa.array(range(table.num_rows)))
    first_rows = indexed.group_by("id").aggregate([("_row", "min")]).column("_row_min")
    return table.take(first_rows.take(pc.sort_indices(first_rows)))


def download_default_csv() -> Path:
    import kagglehub

    dataset_dir = Path(kagglehub.dataset_download(DEFAULT_KAGGLE_DATASET))
    return dataset_dir / DEFAULT_CSV_NAME


def main() -> None:
    input_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else download_default_csv()
    output_parquet = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_OUTPUT)
    build_dataset(input_csv, output_parquet)


if __name__ == "__main__":
    main()
