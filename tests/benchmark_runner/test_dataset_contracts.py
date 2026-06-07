from __future__ import annotations

import pandas as pd
import pytest

from tools.benchmark_runner.datasets.base import TimeSeriesDataset, validate_canonical_values


def test_time_series_dataset_requires_the_shared_canonical_columns():
    values = pd.DataFrame(
        {
            "item_id": ["series"],
            "timestamp": [pd.Timestamp("2024-01-01")],
            "variable": ["target"],
        }
    )

    with pytest.raises(ValueError, match="value"):
        validate_canonical_values(values)


def test_time_series_dataset_contract_is_source_agnostic():
    values = pd.DataFrame(
        {
            "item_id": ["series", "series"],
            "timestamp": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "variable": ["target", "target"],
            "value": [1.0, 2.0],
        }
    )

    dataset = TimeSeriesDataset(
        values=validate_canonical_values(values),
        frequency="D",
        provenance={"source_type": "local"},
    )

    assert list(dataset.values.columns) == ["item_id", "timestamp", "variable", "value"]
    assert dataset.frequency == "D"
    assert dataset.provenance["source_type"] == "local"

