from __future__ import annotations

import argparse
import copy
from dataclasses import is_dataclass, replace
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .datasets import DatasetUnavailableError, InsufficientDataError, build_windows, load_dataset_object_for_task
from .gifteval_gluonts import build_gifteval_windows, effective_target_streams
from .metadata import generate_tasks, load_suite
from .metrics import mae
from .model_adapters import MissingDependencyError, UnsupportedTaskError, get_adapter
from .results import build_completed_result, build_failed_result, build_skipped_result


def build_dry_run_summary(tasks: Sequence[Any]) -> dict[str, Any]:
    return {
        "task_count": len(tasks),
        "models": _counts(tasks, "model_id"),
        "datasets": _counts(tasks, "suite_dataset_id"),
        "io_modes": _counts(tasks, "io_mode"),
        "windows": _counts(tasks, "window_id"),
        "horizons": _counts(tasks, "horizon_id"),
        "run_ids": [_task_value(task, "run_id", None) for task in tasks if _task_value(task, "run_id", None)],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        suite = _load_suite_for_cli(args.suite)
        tasks = generate_tasks(
            suite,
            include_curation_required=args.include_curation_required,
            dataset_ids=args.dataset,
            model_ids=args.model,
            io_modes=args.io_mode,
            horizons=args.window,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.max_tasks is not None:
        tasks = tasks[: args.max_tasks]

    if args.dry_run:
        print(json.dumps(build_dry_run_summary(tasks), indent=2, sort_keys=True))
        return 0

    for task in tasks:
        result = _run_task(task, suite, args)
        _write_cli_result(result, args.output_dir)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Paper 1 zero-shot benchmark tasks.")
    parser.add_argument("--suite", required=True, help="Path to the benchmark suite JSON file.")
    parser.add_argument("--output-dir", default="data/benchmark/runs/paper1-v0", help="Directory for result JSON files.")
    parser.add_argument("--data-root", default="data", help="Root directory for local dataset files.")
    parser.add_argument("--model", action="append", help="Model id filter. Repeat to include multiple models.")
    parser.add_argument("--dataset", action="append", help="Suite dataset id filter. Repeat to include multiple datasets.")
    parser.add_argument("--io-mode", action="append", help="IO mode filter. Repeat to include multiple modes.")
    parser.add_argument(
        "--window",
        "--horizon",
        dest="window",
        action="append",
        help="Evaluation window id filter. --horizon is kept as a compatibility alias.",
    )
    parser.add_argument("--include-curation-required", action="store_true", help="Include datasets marked curation_required.")
    parser.add_argument("--dry-run", action="store_true", help="Print a JSON task summary without loading data or models.")
    parser.add_argument("--max-tasks", type=int, help="Limit the number of generated tasks to execute or summarize.")
    parser.add_argument("--device-map", default="auto", help="Device map passed to model adapters.")
    parser.add_argument("--num-windows", type=int, help="Override the number of chronological windows per task.")
    return parser


def _load_suite_for_cli(path: str | Path) -> dict[str, Any]:
    suite = load_suite(path)
    suite.setdefault("evaluation_modes", ["zero_shot"])
    return suite


def _run_task(task: Any, suite: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    try:
        dataset = load_dataset_object_for_task(task, suite, data_root=args.data_root)
        frame = dataset.values
        run_task = _task_with_effective_targets(task, frame)
        if _task_value(task, "source_benchmark", None) == "gift_eval":
            windows = build_gifteval_windows(dataset, run_task, num_windows=args.num_windows)
        else:
            windows = build_windows(frame, run_task, num_windows=args.num_windows)
    except DatasetUnavailableError as exc:
        return build_skipped_result(task, _skip_reason(exc.reason), str(exc))
    except InsufficientDataError as exc:
        return build_skipped_result(task, "data_unavailable", str(exc))

    try:
        adapter = _get_cached_adapter(task, args)
    except MissingDependencyError as exc:
        return build_skipped_result(task, "missing_dependency", str(exc), model_runtime=_adapter_runtime(exc))
    except UnsupportedTaskError as exc:
        return build_skipped_result(task, _unsupported_reason(exc), str(exc), model_runtime=_adapter_runtime(exc))

    actual_values: list[float] = []
    predicted_values: list[float] = []
    try:
        for window in windows:
            ground_truth = _target_frame(window["ground_truth"], run_task)
            future_df = window["ground_truth"].drop(columns=["value"])
            window_task = _task_with_effective_context(run_task, window["context"])
            forecast = adapter.predict(window["context"], future_df, window_task)
            actual, predicted = _align_forecast(ground_truth, forecast)
            actual_values.extend(actual)
            predicted_values.extend(predicted)
        metrics = {"MAE": mae(actual_values, predicted_values)}
        runtime = {
            "adapter": adapter.__class__.__name__,
            "device_map": args.device_map,
            "num_windows": len(windows),
            "window_policy": _task_value(task, "context_policy", "fixed_length"),
        }
        return build_completed_result(task, metrics, runtime)
    except MissingDependencyError as exc:
        return build_skipped_result(task, "missing_dependency", str(exc), model_runtime=_adapter_runtime(exc))
    except UnsupportedTaskError as exc:
        return build_skipped_result(task, _unsupported_reason(exc), str(exc), model_runtime=_adapter_runtime(exc))
    except Exception as exc:
        return build_failed_result(task, exc.__class__.__name__, str(exc), model_runtime={"device_map": args.device_map})


def _target_frame(frame: pd.DataFrame, task: Any) -> pd.DataFrame:
    target_streams = list(_task_value(task, "target_streams", []) or [])
    if not target_streams:
        return frame
    return frame[frame["variable"].isin(target_streams)].reset_index(drop=True)


def _align_forecast(ground_truth: pd.DataFrame, forecast: pd.DataFrame) -> tuple[list[float], list[float]]:
    required = {"item_id", "timestamp", "variable", "prediction"}
    missing = sorted(required - set(forecast.columns))
    if missing:
        raise ValueError(f"forecast is missing required columns: {', '.join(missing)}")

    ground_truth = ground_truth.copy()
    forecast = forecast[["item_id", "timestamp", "variable", "prediction"]].copy()
    ground_truth["value"] = pd.to_numeric(ground_truth["value"], errors="raise")
    valid_labels = np.isfinite(ground_truth["value"].to_numpy(dtype=float))
    if not valid_labels.any():
        raise ValueError("ground-truth target rows contain no finite labels after masking")

    ground_truth = ground_truth.loc[valid_labels].reset_index(drop=True)
    for frame in (ground_truth, forecast):
        frame["item_id"] = frame["item_id"].astype(str)
        frame["variable"] = frame["variable"].astype(str)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])

    joined = ground_truth.merge(
        forecast,
        on=["item_id", "timestamp", "variable"],
        how="inner",
    )
    if len(joined) != len(ground_truth):
        missing_count = len(ground_truth) - len(joined)
        raise ValueError(
            "forecast does not cover every finite ground-truth target row; "
            f"missing {missing_count} of {len(ground_truth)} rows"
        )
    joined["prediction"] = pd.to_numeric(joined["prediction"], errors="raise")
    if not np.isfinite(joined["prediction"].to_numpy(dtype=float)).all():
        raise ValueError("forecast contains non-finite predictions")
    return joined["value"].tolist(), joined["prediction"].tolist()


def _write_cli_result(result: dict[str, Any], output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    result_path = output_path / f"{result['run_id']}.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result_path


def _get_cached_adapter(task: Any, args: argparse.Namespace) -> Any:
    cache = getattr(args, "adapter_cache", None)
    if cache is None:
        return get_adapter(task.model_id, device_map=args.device_map)

    key = (str(task.model_id), str(args.device_map))
    if key not in cache:
        cache[key] = get_adapter(task.model_id, device_map=args.device_map)
    return cache[key]


def _task_with_effective_targets(task: Any, frame: pd.DataFrame) -> Any:
    targets = effective_target_streams(frame, task)
    if targets == list(_task_value(task, "target_streams", []) or []):
        return task
    if is_dataclass(task):
        return replace(task, target_streams=targets, observed_streams=targets)
    task_copy = copy.copy(task)
    task_copy.target_streams = targets
    task_copy.observed_streams = targets
    return task_copy


def _task_with_effective_context(task: Any, context: pd.DataFrame) -> Any:
    context_length = _effective_context_length(context)
    if is_dataclass(task):
        return replace(task, lookback_window=context_length)
    task_copy = copy.copy(task)
    setattr(task_copy, "lookback_window", context_length)
    setattr(task_copy, "context_length", context_length)
    return task_copy


def _effective_context_length(context: pd.DataFrame) -> int:
    if context.empty:
        return 0
    if {"item_id", "variable", "timestamp"}.issubset(context.columns):
        counts = context.groupby(["item_id", "variable"], dropna=False)["timestamp"].nunique()
        return int(counts.min()) if not counts.empty else 0
    return int(context["timestamp"].nunique()) if "timestamp" in context.columns else len(context)


def _skip_reason(reason: str) -> str:
    allowed = {"missing_dependency", "unsupported_model_frequency_window", "curation_required", "data_unavailable"}
    return reason if reason in allowed else "data_unavailable"


def _unsupported_reason(exc: UnsupportedTaskError) -> str:
    allowed = {
        "unsupported_model_frequency_window",
        "unsupported_api_version",
        "unsupported_frequency",
        "unsupported_multitarget",
        "unsupported_runtime_api",
        "unsupported_window",
        "resource_budget_exceeded",
    }
    return exc.reason if exc.reason in allowed else "unsupported_model_frequency_window"


def _adapter_runtime(exc: Exception) -> dict[str, Any]:
    runtime: dict[str, Any] = {}
    for attr in ("model_id", "packages", "source_url", "reason", "details"):
        if hasattr(exc, attr):
            value = getattr(exc, attr)
            runtime[attr] = list(value) if isinstance(value, tuple) else value
    return runtime


def _counts(tasks: Sequence[Any], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(_task_value(task, field)) for task in tasks).items()))


def _task_value(task: Any, field: str, default: Any = None) -> Any:
    value = getattr(task, field, default)
    return value() if callable(value) else value


if __name__ == "__main__":
    raise SystemExit(main())
