from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

import pandas as pd
import pytest

from tools.benchmark_runner.datasets.base import read_huggingface_csv
from tools.benchmark_runner.datasets.electricity import ElectricityDataset
from tools.benchmark_runner.datasets.etth1 import ETTh1Dataset
from tools.benchmark_runner.datasets.exchange import ExchangeDataset
from tools.benchmark_runner.datasets.ili import ILIDataset
from tools.benchmark_runner.datasets.m4 import M4DailyDataset, M4HourlyDataset, M4MonthlyDataset
from tools.benchmark_runner.datasets.traffic import TrafficDataset
from tools.benchmark_runner.datasets.weather_jena import WeatherJenaDataset


REPO_ID = "thuml/Time-Series-Library"
REVISION = "a" * 40


def _record(
    benchmark_id: str,
    files: dict[str, str],
    class_name: str,
    module: str,
) -> dict:
    return {
        "benchmark_id": benchmark_id,
        "dataset_id": benchmark_id,
        "implementation": {"module": module, "class": class_name},
        "source": {
            "type": "huggingface",
            "repo_id": REPO_ID,
            "revision": REVISION,
            "files": files,
            "url": f"https://huggingface.co/datasets/{REPO_ID}",
        },
    }


def _reader_for(frames: dict[str, pd.DataFrame], calls: list[str]) -> Callable:
    def read_csv(url: str, **kwargs) -> pd.DataFrame:
        calls.append(url)
        for path, frame in frames.items():
            if url.endswith(path):
                return frame.copy()
        raise AssertionError(f"Unexpected Hugging Face URL: {url}")

    return read_csv


def test_shared_huggingface_reader_streams_through_requests(monkeypatch):
    class Response:
        def __init__(self):
            self.raw = BytesIO(b"date,OT\n2024-01-01,1.0\n")
            self.raw.decode_content = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def raise_for_status(self):
            return None

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("tools.benchmark_runner.datasets.base.requests.get", get)

    frame = read_huggingface_csv("https://huggingface.co/example.csv")

    assert frame.to_dict("records") == [{"date": "2024-01-01", "OT": 1.0}]
    assert calls == [
        (
            "https://huggingface.co/example.csv",
            {"stream": True, "timeout": (10, 120)},
        )
    ]


@pytest.mark.parametrize(
    ("dataset_class", "benchmark_id", "file_path", "frequency", "columns"),
    [
        (
            ETTh1Dataset,
            "etth1_thuml",
            "ETT-small/ETTh1.csv",
            "h",
            {"date": ["2024-01-01", "2024-01-01 01:00"], "HUFL": [1.0, 2.0], "OT": [3.0, 4.0]},
        ),
        (
            ElectricityDataset,
            "electricity_thuml",
            "electricity/electricity.csv",
            "h",
            {"date": ["2024-01-01", "2024-01-01 01:00"], "0": [1.0, 2.0], "OT": [3.0, 4.0]},
        ),
        (
            TrafficDataset,
            "traffic_thuml",
            "traffic/traffic.csv",
            "h",
            {"date": ["2024-01-01", "2024-01-01 01:00"], "0": [1.0, 2.0], "OT": [3.0, 4.0]},
        ),
        (
            WeatherJenaDataset,
            "weather_jena_thuml",
            "weather/weather.csv",
            "10min",
            {"date": ["2024-01-01", "2024-01-01 00:10"], "p (mbar)": [1.0, 2.0], "OT": [3.0, 4.0]},
        ),
        (
            ExchangeDataset,
            "exchange_rate_thuml",
            "exchange_rate/exchange_rate.csv",
            "D",
            {"date": ["2024-01-01", "2024-01-02"], "0": [1.0, 2.0], "OT": [3.0, 4.0]},
        ),
        (
            ILIDataset,
            "ili_thuml",
            "illness/national_illness.csv",
            "W",
            {"date": ["2024-01-07", "2024-01-14"], "% WEIGHTED ILI": [1.0, 2.0], "OT": [3.0, 4.0]},
        ),
    ],
)
def test_wide_huggingface_datasets_share_the_canonical_contract(
    dataset_class,
    benchmark_id,
    file_path,
    frequency,
    columns,
):
    calls: list[str] = []
    record = _record(
        benchmark_id,
        {"data": file_path},
        dataset_class.__name__,
        dataset_class.__module__,
    )

    dataset = dataset_class(record, csv_reader=_reader_for({file_path: pd.DataFrame(columns)}, calls)).load()

    assert list(dataset.values.columns) == ["item_id", "timestamp", "variable", "value"]
    assert dataset.frequency == frequency
    assert dataset.values["item_id"].unique().tolist() == [benchmark_id]
    assert set(dataset.values["variable"]) == set(columns) - {"date"}
    assert dataset.provenance["source_type"] == "huggingface"
    assert dataset.provenance["revision"] == REVISION
    assert len(calls) == 1
    assert f"/resolve/{REVISION}/{file_path}" in calls[0]


def test_weather_normalizes_unicode_units_to_suite_variable_names():
    file_path = "weather/weather.csv"
    record = _record(
        "weather_jena_thuml",
        {"data": file_path},
        "WeatherJenaDataset",
        WeatherJenaDataset.__module__,
    )
    raw = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "SWDR (W/m²)": [1.0],
            "PAR (µmol/m²/s)": [2.0],
            "max. PAR (µmol/m²/s)": [3.0],
            "OT": [4.0],
        }
    )

    dataset = WeatherJenaDataset(record, csv_reader=_reader_for({file_path: raw}, [])).load()

    assert set(dataset.values["variable"]) == {
        "SWDR (W/m2)",
        "PAR (umol/m2/s)",
        "max. PAR (umol/m2/s)",
        "OT",
    }


@pytest.mark.parametrize(
    ("dataset_class", "prefix", "frequency"),
    [
        (M4HourlyDataset, "Hourly", "h"),
        (M4DailyDataset, "Daily", "D"),
        (M4MonthlyDataset, "Monthly", "MS"),
    ],
)
def test_m4_subsets_preserve_official_train_test_splits(dataset_class, prefix, frequency):
    train_path = f"m4/{prefix}-train.csv"
    test_path = f"m4/{prefix}-test.csv"
    record = _record(
        f"m4_{prefix.lower()}_thuml",
        {"train": train_path, "test": test_path},
        dataset_class.__name__,
        dataset_class.__module__,
    )
    calls: list[str] = []
    reader = _reader_for(
        {
            train_path: pd.DataFrame({"V1": [f"{prefix[0]}1", f"{prefix[0]}2"], "V2": [1.0, 4.0], "V3": [2.0, 5.0], "V4": [3.0, None]}),
            test_path: pd.DataFrame({"V1": [f"{prefix[0]}1", f"{prefix[0]}2"], "V2": [10.0, 40.0], "V3": [11.0, None]}),
        },
        calls,
    )

    dataset = dataset_class(record, csv_reader=reader).load()

    assert dataset.frequency == frequency
    assert pd.api.types.is_datetime64_any_dtype(dataset.values["timestamp"])
    expected_timestamps = list(pd.date_range("2000-01-01", periods=5, freq=frequency))
    assert dataset.values.loc[dataset.values["item_id"].eq(f"{prefix[0]}1"), "timestamp"].tolist() == expected_timestamps
    assert dataset.values.loc[dataset.values["item_id"].eq(f"{prefix[0]}1"), "value"].tolist() == [1.0, 2.0, 3.0, 10.0, 11.0]
    assert dataset.splits is not None
    assert dataset.splits.loc[dataset.splits["item_id"].eq(f"{prefix[0]}1"), "split"].tolist() == [
        "train",
        "train",
        "train",
        "test",
        "test",
    ]
    assert len(calls) == 2
