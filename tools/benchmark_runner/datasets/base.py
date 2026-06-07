from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote

import pandas as pd
import requests


NORMALIZED_COLUMNS = ["item_id", "timestamp", "variable", "value"]
DEFAULT_DATASET_REGISTRY = Path("data/benchmark/dataset-metadata.json")


class DatasetUnavailableError(RuntimeError):
    """Raised when a dataset source cannot be loaded."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class InsufficientDataError(RuntimeError):
    """Raised when a normalized dataset cannot satisfy a task window."""

    reason = "insufficient_data"


@dataclass(frozen=True)
class TimeSeriesDataset:
    """Source-independent dataset representation consumed by benchmark tasks."""

    values: pd.DataFrame
    frequency: str
    provenance: dict[str, Any]
    splits: pd.DataFrame | None = None
    static_features: pd.DataFrame | None = None


class BaseDataset(ABC):
    """Acquire dataset-specific inputs and normalize them to one contract."""

    frequency: str

    def __init__(
        self,
        registry_record: Mapping[str, Any],
        *,
        csv_reader: Callable[..., pd.DataFrame] | None = None,
    ):
        self.registry_record = dict(registry_record)
        self.csv_reader = csv_reader or pd.read_csv

    def load(self) -> TimeSeriesDataset:
        raw = self.read_raw()
        dataset = self.to_dataset(raw)
        return TimeSeriesDataset(
            values=validate_canonical_values(dataset.values),
            frequency=dataset.frequency,
            provenance=dict(dataset.provenance),
            splits=_validate_splits(dataset.splits),
            static_features=dataset.static_features,
        )

    @abstractmethod
    def read_raw(self) -> Any:
        """Acquire source-specific raw inputs."""

    @abstractmethod
    def to_dataset(self, raw: Any) -> TimeSeriesDataset:
        """Convert raw inputs into the source-independent contract."""


class HuggingFaceDataset(BaseDataset):
    """Base class for raw files streamed from a pinned Hugging Face dataset repo."""

    def __init__(
        self,
        registry_record: Mapping[str, Any],
        *,
        csv_reader: Callable[..., pd.DataFrame] | None = None,
    ):
        super().__init__(registry_record, csv_reader=csv_reader or read_huggingface_csv)
        source = self.registry_record.get("source", {})
        if source.get("type") != "huggingface":
            raise ValueError("HuggingFaceDataset requires source.type='huggingface'")
        for field in ("repo_id", "revision", "files", "url"):
            if not source.get(field):
                raise ValueError(f"Hugging Face source is missing required field: {field}")
        self.source = source

    @property
    def item_id(self) -> str:
        return str(self.registry_record.get("benchmark_id") or self.registry_record["dataset_id"])

    def read_huggingface_csv(self, file_key: str, **kwargs: Any) -> pd.DataFrame:
        return self.csv_reader(self.file_url(file_key), **kwargs)

    def file_url(self, file_key: str) -> str:
        files = self.source["files"]
        if file_key not in files:
            raise ValueError(f"Hugging Face source has no file named {file_key!r}")
        repo_id = quote(str(self.source["repo_id"]), safe="/")
        revision = quote(str(self.source["revision"]), safe="")
        path = quote(str(files[file_key]), safe="/")
        return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{path}"

    def provenance(self, file_keys: Iterable[str]) -> dict[str, Any]:
        keys = list(file_keys)
        return {
            "source_type": "huggingface",
            "repo_id": self.source["repo_id"],
            "revision": self.source["revision"],
            "source_url": self.source["url"],
            "files": {key: self.source["files"][key] for key in keys},
            "resolved_urls": {key: self.file_url(key) for key in keys},
        }


class WideHuggingFaceDataset(HuggingFaceDataset):
    """Shared implementation for date-plus-numeric-channel CSV datasets."""

    source_file_key = "data"
    timestamp_column = "date"

    def read_raw(self) -> pd.DataFrame:
        return self.read_huggingface_csv(self.source_file_key)

    def to_dataset(self, raw: pd.DataFrame) -> TimeSeriesDataset:
        if self.timestamp_column not in raw.columns:
            raise ValueError(f"Missing timestamp column: {self.timestamp_column}")
        variables = [column for column in raw.columns if column != self.timestamp_column]
        if not variables:
            raise ValueError("Dataset contains no value columns")
        values = wide_csv_to_long(
            raw,
            timestamp_col=self.timestamp_column,
            item_id=self.item_id,
            variables=variables,
        )
        return TimeSeriesDataset(
            values=values,
            frequency=self.frequency,
            provenance=self.provenance([self.source_file_key]),
        )


def read_huggingface_csv(url: str, **kwargs: Any) -> pd.DataFrame:
    """Read a Hugging Face CSV through requests' certifi-backed TLS stack."""

    with requests.get(url, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        response.raw.decode_content = True
        return pd.read_csv(response.raw, **kwargs)


def validate_canonical_values(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in NORMALIZED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Dataset frame must contain normalized columns: {', '.join(missing)} missing")

    values = frame[NORMALIZED_COLUMNS].copy()
    if values[["item_id", "timestamp", "variable", "value"]].isnull().any().any():
        raise ValueError("Canonical dataset values cannot contain null keys or values")

    values["item_id"] = values["item_id"].astype(str)
    values["variable"] = values["variable"].astype(str)
    values["value"] = pd.to_numeric(values["value"], errors="raise")
    if values["timestamp"].dtype == object:
        values["timestamp"] = _coerce_timestamp(values["timestamp"])

    duplicate_keys = values.duplicated(["item_id", "timestamp", "variable"])
    if duplicate_keys.any():
        raise ValueError("Canonical dataset contains duplicate item_id/timestamp/variable keys")

    return values.sort_values(["item_id", "variable", "timestamp"]).reset_index(drop=True)


def wide_csv_to_long(
    df: pd.DataFrame,
    timestamp_col: str | None,
    item_id: str,
    variables: Iterable[str],
    *,
    variable_name: str | None = None,
) -> pd.DataFrame:
    """Normalize a wide dataframe to item_id/timestamp/variable/value rows."""

    variables = list(variables)
    missing = [column for column in variables if column not in df.columns]
    if missing:
        raise ValueError(f"Missing variable columns: {', '.join(missing)}")

    if item_id in df.columns:
        item_id_col = item_id
        id_vars = [item_id_col]
    else:
        item_id_col = "item_id"
        df = df.copy()
        df[item_id_col] = item_id
        id_vars = [item_id_col]

    if timestamp_col is not None:
        if timestamp_col not in df.columns:
            raise ValueError(f"Missing timestamp column: {timestamp_col}")
        id_vars.append(timestamp_col)
        melted = df.melt(id_vars=id_vars, value_vars=variables, var_name="variable", value_name="value")
        melted = melted.rename(columns={item_id_col: "item_id", timestamp_col: "timestamp"})
        melted["timestamp"] = _coerce_timestamp(melted["timestamp"])
    else:
        melted = df.melt(id_vars=id_vars, value_vars=variables, var_name="_wide_step", value_name="value")
        melted = melted.rename(columns={item_id_col: "item_id"})
        step_order = {column: index + 1 for index, column in enumerate(variables)}
        melted["timestamp"] = melted["_wide_step"].map(step_order)
        melted["variable"] = variable_name or melted["_wide_step"]
        melted = melted.drop(columns=["_wide_step"])

    variable_order = {variable: index for index, variable in enumerate(variables)}
    melted["_variable_order"] = melted["variable"].map(variable_order).fillna(0)
    return (
        melted[NORMALIZED_COLUMNS + ["_variable_order"]]
        .dropna(subset=["value"])
        .sort_values(["item_id", "_variable_order", "timestamp"])
        .drop(columns=["_variable_order"])
        .reset_index(drop=True)
    )


def validate_task_window(frame: pd.DataFrame, task: Any) -> None:
    frame = validate_canonical_values(frame)
    lookback = int(_task_value(task, "lookback_window"))
    horizon = int(_task_value(task, "forecast_horizon"))
    required = lookback + horizon
    target_streams = _task_value(task, "target_streams", None) or sorted(frame["variable"].unique())

    target_frame = frame[frame["variable"].isin(target_streams)]
    if target_frame.empty:
        raise InsufficientDataError(f"No target streams found for task: {target_streams}")

    counts = target_frame.groupby(["item_id", "variable"], dropna=False)["timestamp"].nunique()
    shortest = int(counts.min()) if not counts.empty else 0
    if shortest < required:
        raise InsufficientDataError(
            f"Task requires at least {required} timestamps per item/target; shortest series has {shortest}"
        )


def build_windows(
    frame: pd.DataFrame,
    task: Any,
    *,
    num_windows: int = 1,
    stride: int | None = None,
) -> list[dict[str, pd.DataFrame]]:
    """Build chronological holdout windows from the tail of a normalized frame."""

    if num_windows < 1:
        raise ValueError("num_windows must be at least 1")
    stride = stride or int(_task_value(task, "forecast_horizon"))
    if stride < 1:
        raise ValueError("stride must be at least 1")

    validate_task_window(frame, task)
    lookback = int(_task_value(task, "lookback_window"))
    horizon = int(_task_value(task, "forecast_horizon"))
    required = lookback + horizon
    timestamps = sorted(frame["timestamp"].drop_duplicates())

    windows: list[dict[str, pd.DataFrame]] = []
    end = len(timestamps)
    for index in range(num_windows):
        window_end = end - index * stride
        window_start = window_end - required
        if window_start < 0:
            break
        context_times = set(timestamps[window_start : window_start + lookback])
        truth_times = set(timestamps[window_start + lookback : window_end])
        windows.append(
            {
                "window_index": index,
                "context": _slice_times(frame, context_times),
                "ground_truth": _slice_times(frame, truth_times),
            }
        )

    if len(windows) < num_windows:
        raise InsufficientDataError(f"Requested {num_windows} windows but only {len(windows)} fit")
    return windows


def load_dataset_object_for_task(
    task: Any,
    suite: dict[str, Any],
    data_root: str | Path = "data",
    *,
    registry_path: str | Path = DEFAULT_DATASET_REGISTRY,
) -> TimeSeriesDataset:
    """Load a task through its registered dataset class or local compatibility path."""

    suite_dataset = _suite_dataset_for_task(task, suite)
    if suite_dataset.get("curation_required"):
        raise DatasetUnavailableError(
            "curation_required",
            f"{suite_dataset['suite_dataset_id']} requires curation",
        )

    benchmark_id = suite_dataset.get("benchmark_id")
    if benchmark_id:
        registry_record = _load_registry_record(
            benchmark_id,
            _task_value(task, "tsc_dataset_id"),
            Path(registry_path),
        )
        implementation = registry_record.get("implementation")
        if not implementation:
            raise DatasetUnavailableError(
                "data_unavailable",
                f"Dataset {registry_record['dataset_id']} has no registered implementation",
            )
        try:
            module = importlib.import_module(implementation["module"])
            dataset_class = getattr(module, implementation["class"])
            return dataset_class(registry_record).load()
        except DatasetUnavailableError:
            raise
        except Exception as exc:
            raise DatasetUnavailableError(
                "data_unavailable",
                f"Failed to load dataset {registry_record['dataset_id']}: {exc}",
            ) from exc

    data_path = _resolve_dataset_path(suite_dataset, Path(data_root))
    if data_path is not None:
        return _load_local_compatibility_dataset(suite_dataset, data_path)

    raise DatasetUnavailableError(
        "data_unavailable",
        f"Dataset {_task_value(task, 'tsc_dataset_id')} has no benchmark_id or local path",
    )


def load_dataset_for_task(
    task: Any,
    suite: dict[str, Any],
    data_root: str | Path = "data",
    *,
    registry_path: str | Path = DEFAULT_DATASET_REGISTRY,
) -> pd.DataFrame:
    """Compatibility wrapper returning only canonical values."""

    return load_dataset_object_for_task(
        task,
        suite,
        data_root=data_root,
        registry_path=registry_path,
    ).values


def _load_registry_record(
    benchmark_id: str | None,
    dataset_id: str,
    registry_path: Path,
) -> dict[str, Any]:
    try:
        datasets = json.loads(registry_path.read_text(encoding="utf-8"))["datasets"]
    except FileNotFoundError as exc:
        raise DatasetUnavailableError("data_unavailable", f"Dataset registry does not exist: {registry_path}") from exc

    if benchmark_id:
        matches = [dataset for dataset in datasets if dataset.get("benchmark_id") == benchmark_id]
        key_description = f"benchmark_id={benchmark_id}"
    else:
        matches = [dataset for dataset in datasets if dataset.get("dataset_id") == dataset_id]
        key_description = f"dataset_id={dataset_id}"
    if not matches:
        raise DatasetUnavailableError("data_unavailable", f"Dataset is not registered: {key_description}")
    if len(matches) != 1:
        raise DatasetUnavailableError(
            "data_unavailable",
            f"Dataset registry key is ambiguous: {key_description} has {len(matches)} records",
        )
    return matches[0]


def _load_local_compatibility_dataset(dataset: dict[str, Any], data_path: Path) -> TimeSeriesDataset:
    if not data_path.exists():
        raise DatasetUnavailableError("data_unavailable", f"Dataset file does not exist: {data_path}")
    if data_path.suffix.lower() not in {".csv", ".txt"}:
        raise DatasetUnavailableError("unsupported_format", f"Unsupported dataset format: {data_path.suffix}")

    raw = pd.read_csv(data_path)
    if set(NORMALIZED_COLUMNS).issubset(raw.columns):
        values = validate_canonical_values(raw)
    else:
        variables = _dataset_variables(dataset, raw)
        timestamp_col = _timestamp_column(dataset, raw)
        values = validate_canonical_values(
            wide_csv_to_long(
                raw,
                timestamp_col=timestamp_col,
                item_id=_item_id(dataset),
                variables=variables,
            )
        )
    return TimeSeriesDataset(
        values=values,
        frequency=str(dataset.get("frequency_rule", "unknown")),
        provenance={"source_type": "local", "path": str(data_path)},
    )


def _validate_splits(splits: pd.DataFrame | None) -> pd.DataFrame | None:
    if splits is None:
        return None
    required = ["item_id", "timestamp", "split"]
    missing = [column for column in required if column not in splits.columns]
    if missing:
        raise ValueError(f"Dataset splits are missing columns: {', '.join(missing)}")
    result = splits[required].copy()
    if result.isnull().any().any():
        raise ValueError("Dataset splits cannot contain null values")
    if result.duplicated(["item_id", "timestamp"]).any():
        raise ValueError("Dataset splits contain duplicate item_id/timestamp keys")
    return result.sort_values(["item_id", "timestamp"]).reset_index(drop=True)


def _coerce_timestamp(values: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(values)
    except (TypeError, ValueError):
        return values


def _slice_times(frame: pd.DataFrame, timestamps: set[Any]) -> pd.DataFrame:
    return frame[frame["timestamp"].isin(timestamps)].sort_values(["item_id", "variable", "timestamp"]).reset_index(drop=True)


def _task_value(task: Any, key: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(key, default)
    return getattr(task, key, default)


def _suite_dataset_for_task(task: Any, suite: dict[str, Any]) -> dict[str, Any]:
    suite_dataset_id = _task_value(task, "suite_dataset_id")
    tsc_dataset_id = _task_value(task, "tsc_dataset_id")
    for dataset in suite.get("datasets", []):
        if dataset.get("suite_dataset_id") == suite_dataset_id or dataset.get("tsc_dataset_id") == tsc_dataset_id:
            return dataset
    raise DatasetUnavailableError("dataset_not_in_suite", f"Dataset not found in suite: {suite_dataset_id or tsc_dataset_id}")


def _resolve_dataset_path(dataset: dict[str, Any], data_root: Path) -> Path | None:
    for key in ("path", "local_path", "data_path", "file_path", "csv_path"):
        value = dataset.get(key)
        if value:
            path = Path(value)
            return path if path.is_absolute() else data_root / path
    return None


def _dataset_variables(dataset: dict[str, Any], raw: pd.DataFrame) -> list[str]:
    configured = dataset.get("observed_streams") or dataset.get("target_streams") or dataset.get("variables")
    if configured:
        existing = [column for column in configured if column in raw.columns]
        if existing:
            return existing

    timestamp_col = _timestamp_column(dataset, raw)
    id_col = dataset.get("item_id_col") or dataset.get("series_id_col")
    excluded = {column for column in (timestamp_col, id_col) if column}
    numeric = [column for column in raw.columns if column not in excluded and pd.api.types.is_numeric_dtype(raw[column])]
    return numeric or [column for column in raw.columns if column not in excluded]


def _timestamp_column(dataset: dict[str, Any], raw: pd.DataFrame) -> str | None:
    configured = dataset.get("timestamp_col") or dataset.get("time_col") or dataset.get("date_col")
    if configured:
        return configured
    for candidate in ("timestamp", "date", "datetime", "time"):
        if candidate in raw.columns:
            return candidate
    return None


def _item_id(dataset: dict[str, Any]) -> str:
    return (
        dataset.get("item_id_col")
        or dataset.get("series_id_col")
        or dataset.get("suite_dataset_id")
        or dataset.get("tsc_dataset_id")
        or "series"
    )
