from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .datasets.base import InsufficientDataError, TimeSeriesDataset, build_windows


TEST_SPLIT = 0.1
MAX_WINDOWS = 20


def build_gifteval_windows(
    dataset: TimeSeriesDataset,
    task: Any,
    *,
    num_windows: int | None = None,
) -> list[dict[str, pd.DataFrame]]:
    """Build Gift-Eval test windows using GluonTS split semantics when available."""

    task = _task_with_effective_targets(task, dataset.values)
    windows = int(num_windows or _gift_eval_windows(dataset, task))
    if windows < 1:
        raise ValueError("Gift-Eval windows must be at least 1")
    _validate_gifteval_window_feasibility(dataset, task, windows)

    if dataset.gluonts_entries:
        try:
            return _build_with_gluonts(dataset, task, windows)
        except ImportError:
            pass

    return build_windows(dataset.values, _task_with_gifteval_windows(task, windows), num_windows=windows)


def _build_with_gluonts(
    dataset: TimeSeriesDataset,
    task: Any,
    windows: int,
) -> list[dict[str, pd.DataFrame]]:
    from gluonts.dataset.common import ListDataset
    from gluonts.dataset.split import split

    horizon = int(_task_value(task, "forecast_horizon"))
    entries = dataset.gluonts_entries or []
    if not entries:
        raise InsufficientDataError("Gift-Eval dataset has no GluonTS entries")

    gluonts_dataset = ListDataset(entries, freq=dataset.frequency)
    _, test_template = split(gluonts_dataset, offset=-horizon * windows)
    test_data = test_template.generate_instances(
        prediction_length=horizon,
        windows=windows,
        distance=horizon,
    )

    window_parts: list[dict[str, list[pd.DataFrame]]] = [
        {"context": [], "ground_truth": []} for _ in range(windows)
    ]
    labels = list(test_data.label)
    inputs = list(test_data.input)
    if len(labels) != len(inputs):
        raise ValueError("GluonTS test data input/label iterators produced different lengths")
    if len(labels) % windows != 0:
        raise ValueError("GluonTS test data count is not divisible by the number of windows")

    for index, (context_entry, label_entry) in enumerate(zip(inputs, labels)):
        window_index = index % windows
        window_parts[window_index]["context"].append(_entry_to_frame(context_entry))
        window_parts[window_index]["ground_truth"].append(_entry_to_frame(label_entry))

    result = []
    for index, parts in enumerate(window_parts):
        result.append(
            {
                "window_index": index,
                "context": pd.concat(parts["context"], ignore_index=True),
                "ground_truth": pd.concat(parts["ground_truth"], ignore_index=True),
            }
        )
    return result


def _entry_to_frame(entry: dict[str, Any]) -> pd.DataFrame:
    item_id, variable = _decode_item_variable(entry)
    target = list(entry["target"])
    start = _entry_start(entry["start"])
    freq = _entry_freq(entry)
    timestamps = pd.date_range(start=start, periods=len(target), freq=freq)
    return pd.DataFrame(
        {
            "item_id": item_id,
            "timestamp": timestamps,
            "variable": variable,
            "value": target,
        }
    )


def _decode_item_variable(entry: dict[str, Any]) -> tuple[str, str]:
    if entry.get("tsc_item_id") is not None and entry.get("tsc_variable") is not None:
        return str(entry["tsc_item_id"]), str(entry["tsc_variable"])
    item_id = str(entry.get("item_id", ""))
    if "\u001f" in item_id:
        left, right = item_id.rsplit("\u001f", 1)
        return left, right
    return item_id, "target"


def _entry_start(start: Any) -> pd.Timestamp:
    if hasattr(start, "to_timestamp"):
        return pd.Timestamp(start.to_timestamp())
    return pd.Timestamp(start)


def _entry_freq(entry: dict[str, Any]) -> str:
    start = entry.get("start")
    if hasattr(start, "freqstr"):
        return str(start.freqstr)
    if hasattr(start, "freq") and getattr(start.freq, "freqstr", None):
        return str(start.freq.freqstr)
    return "D"


def _gift_eval_windows(dataset: TimeSeriesDataset, task: Any) -> int:
    if str(_task_value(task, "num_windows_policy", "")) == "gift_eval_m4":
        return 1
    explicit = _task_value(task, "num_windows", None)
    if explicit is not None:
        return int(explicit)
    horizon = int(_task_value(task, "forecast_horizon"))
    shortest = _shortest_series_length(dataset.values, task)
    return min(max(1, math.ceil(TEST_SPLIT * shortest / horizon)), MAX_WINDOWS)


def _validate_gifteval_window_feasibility(dataset: TimeSeriesDataset, task: Any, windows: int) -> None:
    horizon = int(_task_value(task, "forecast_horizon"))
    shortest = _shortest_series_length(dataset.values, task)
    required = horizon * windows + 1
    if shortest < required:
        raise InsufficientDataError(
            "Gift-Eval task requires at least "
            f"{required} timestamps per item/target for horizon={horizon} and windows={windows}; "
            f"shortest series has {shortest}"
        )


def _shortest_series_length(frame: pd.DataFrame, task: Any) -> int:
    target_streams = _effective_target_streams(frame, task)
    target_frame = frame[frame["variable"].isin(target_streams)]
    if target_frame.empty:
        raise InsufficientDataError(f"No target streams found for Gift-Eval task: {target_streams}")
    counts = target_frame.groupby(["item_id", "variable"], dropna=False)["timestamp"].nunique()
    return int(counts.min()) if not counts.empty else 0


def effective_target_streams(frame: pd.DataFrame, task: Any) -> list[str]:
    return _effective_target_streams(frame, task)


def _effective_target_streams(frame: pd.DataFrame, task: Any) -> list[str]:
    requested = list(_task_value(task, "target_streams", []) or [])
    available = list(dict.fromkeys(frame["variable"].astype(str)))
    if not requested:
        return available
    if set(requested).issubset(set(available)):
        return requested
    return available


def _task_with_gifteval_windows(task: Any, windows: int) -> Any:
    import copy
    from dataclasses import is_dataclass, replace

    updates = {"num_windows": windows, "num_windows_policy": None, "context_policy": "full_history"}
    if is_dataclass(task):
        return replace(task, **{key: value for key, value in updates.items() if hasattr(task, key)})
    task_copy = copy.copy(task)
    for key, value in updates.items():
        setattr(task_copy, key, value)
    return task_copy


def _task_with_effective_targets(task: Any, frame: pd.DataFrame) -> Any:
    import copy
    from dataclasses import is_dataclass, replace

    targets = _effective_target_streams(frame, task)
    if targets == list(_task_value(task, "target_streams", []) or []):
        return task
    updates = {"target_streams": targets, "observed_streams": targets}
    if is_dataclass(task):
        return replace(task, **{key: value for key, value in updates.items() if hasattr(task, key)})
    task_copy = copy.copy(task)
    for key, value in updates.items():
        setattr(task_copy, key, value)
    return task_copy


def _task_value(task: Any, name: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(name, default)
    return getattr(task, name, default)
