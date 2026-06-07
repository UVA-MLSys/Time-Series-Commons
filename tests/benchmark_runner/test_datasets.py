from types import SimpleNamespace

import pandas as pd
import pytest

from tools.benchmark_runner.datasets import (
    DatasetUnavailableError,
    InsufficientDataError,
    TimeSeriesDataset,
    build_windows,
    load_dataset_for_task,
    validate_task_window,
    wide_csv_to_long,
)


def test_wide_csv_to_long_normalizes_contract_with_literal_item_id():
    wide = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=2, freq="h"),
            "OT": [10.0, 11.0],
            "HUFL": [1.0, 2.0],
        }
    )

    long = wide_csv_to_long(wide, timestamp_col="date", item_id="etth1", variables=["OT", "HUFL"])

    assert list(long.columns) == ["item_id", "timestamp", "variable", "value"]
    assert long.to_dict("records") == [
        {"item_id": "etth1", "timestamp": pd.Timestamp("2024-01-01 00:00:00"), "variable": "OT", "value": 10.0},
        {"item_id": "etth1", "timestamp": pd.Timestamp("2024-01-01 01:00:00"), "variable": "OT", "value": 11.0},
        {"item_id": "etth1", "timestamp": pd.Timestamp("2024-01-01 00:00:00"), "variable": "HUFL", "value": 1.0},
        {"item_id": "etth1", "timestamp": pd.Timestamp("2024-01-01 01:00:00"), "variable": "HUFL", "value": 2.0},
    ]


def test_wide_csv_to_long_supports_item_id_column_for_m4_style_rows():
    wide = pd.DataFrame({"series_id": ["H1", "H2"], "t1": [1, 3], "t2": [2, 4]})

    long = wide_csv_to_long(
        wide,
        timestamp_col=None,
        item_id="series_id",
        variables=["t1", "t2"],
        variable_name="y",
    )

    assert set(long["item_id"]) == {"H1", "H2"}
    assert set(long["variable"]) == {"y"}
    assert long.loc[long["item_id"].eq("H1"), "value"].tolist() == [1, 2]
    assert long.loc[long["item_id"].eq("H1"), "timestamp"].tolist() == [1, 2]


def test_validate_task_window_rejects_frames_that_are_too_short():
    frame = pd.DataFrame(
        {
            "item_id": ["a", "a", "a"],
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D"),
            "variable": ["OT", "OT", "OT"],
            "value": [1.0, 2.0, 3.0],
        }
    )
    task = SimpleNamespace(lookback_window=2, forecast_horizon=2, target_streams=["OT"])

    with pytest.raises(InsufficientDataError, match="requires at least 4"):
        validate_task_window(frame, task)


def test_build_windows_returns_chronological_context_and_ground_truth():
    frame = pd.DataFrame(
        {
            "item_id": ["a"] * 6,
            "timestamp": pd.date_range("2024-01-01", periods=6, freq="D"),
            "variable": ["OT"] * 6,
            "value": range(6),
        }
    )
    task = SimpleNamespace(lookback_window=3, forecast_horizon=2, target_streams=["OT"])

    windows = build_windows(frame, task, num_windows=2, stride=1)

    assert len(windows) == 2
    assert windows[0]["context"]["timestamp"].tolist() == list(pd.date_range("2024-01-02", periods=3, freq="D"))
    assert windows[0]["ground_truth"]["timestamp"].tolist() == list(pd.date_range("2024-01-05", periods=2, freq="D"))
    assert windows[1]["context"]["timestamp"].tolist() == list(pd.date_range("2024-01-01", periods=3, freq="D"))
    assert windows[1]["ground_truth"]["timestamp"].tolist() == list(pd.date_range("2024-01-04", periods=2, freq="D"))


def test_load_dataset_for_task_signals_missing_local_path(tmp_path):
    suite = {
        "datasets": [
            {
                "suite_dataset_id": "paper1_missing",
                "tsc_dataset_id": "missing-dataset",
                "path": "benchmark/missing.csv",
                "target_streams": ["OT"],
            }
        ]
    }
    task = SimpleNamespace(suite_dataset_id="paper1_missing", tsc_dataset_id="missing-dataset")

    with pytest.raises(DatasetUnavailableError) as exc_info:
        load_dataset_for_task(task, suite, data_root=tmp_path)

    assert exc_info.value.reason == "data_unavailable"
    assert "benchmark/missing.csv" in str(exc_info.value)


def test_registered_huggingface_dataset_takes_precedence_over_local_path(tmp_path, monkeypatch):
    registry_path = tmp_path / "dataset-metadata.json"
    registry_path.write_text(
        """
        {
          "datasets": [{
            "dataset_id": "ett-hourly-station-1-etth1",
            "benchmark_id": "etth1_thuml",
            "implementation": {
              "module": "tools.benchmark_runner.datasets.etth1",
              "class": "ETTh1Dataset"
            },
            "source": {
              "type": "huggingface",
              "repo_id": "thuml/Time-Series-Library",
              "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              "files": {"data": "ETT-small/ETTh1.csv"},
              "url": "https://huggingface.co/datasets/thuml/Time-Series-Library"
            }
          }]
        }
        """,
        encoding="utf-8",
    )
    suite = {
        "datasets": [
            {
                "suite_dataset_id": "paper1_etth1",
                "tsc_dataset_id": "ett-hourly-station-1-etth1",
                "benchmark_id": "etth1_thuml",
                "path": "missing-local-file.csv",
            }
        ]
    }
    task = SimpleNamespace(
        suite_dataset_id="paper1_etth1",
        tsc_dataset_id="ett-hourly-station-1-etth1",
    )
    expected = pd.DataFrame(
        {
            "item_id": ["etth1_thuml"],
            "timestamp": [pd.Timestamp("2024-01-01")],
            "variable": ["OT"],
            "value": [1.0],
        }
    )

    monkeypatch.setattr(
        "tools.benchmark_runner.datasets.etth1.ETTh1Dataset.load",
        lambda self: TimeSeriesDataset(expected, "h", {"source_type": "huggingface"}),
    )

    loaded = load_dataset_for_task(task, suite, data_root=tmp_path, registry_path=registry_path)

    pd.testing.assert_frame_equal(loaded, expected)
