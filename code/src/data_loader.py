"""Helpers for loading the challenge's tabular input data."""

from pathlib import Path

import pandas as pd


def load_all_datasets(dataset_dir: str) -> dict[str, pd.DataFrame]:
    """Load every CSV file directly inside ``dataset_dir``.

    The loader intentionally does not join tables or convert any columns.  Those
    decisions belong to later pipeline stages, so this function keeps the raw
    CSV values available to the rest of the application.
    """
    # Sorting makes the loading order deterministic, which is helpful when
    # debugging and when comparing runs.
    csv_paths = sorted(Path(dataset_dir).glob("*.csv"))

    datasets: dict[str, pd.DataFrame] = {}
    for csv_path in csv_paths:
        # A file such as "requests.csv" is returned under the key "requests".
        datasets[csv_path.stem] = pd.read_csv(csv_path)

    return datasets
