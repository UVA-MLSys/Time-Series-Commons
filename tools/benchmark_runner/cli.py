from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .datasets import DatasetUnavailableError, InsufficientDataError, build_windows, load_dataset_for_task
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
            horizons=args.horizon,
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
    parser = argparse.ArgumentParser(description="Run zero-shot forecasting benchmark tasks.")
    parser.add_argument("--suite", required=True, help="Path to the benchmark suite JSON file.")
    parser.add_argument("--output-dir", default="data/benchmark/runs/forecasting-v0", help="Directory for result JSON files.")
    parser.add_argument("--data-root", default="data", help="Root directory for local dataset files.")
    parser.add_argument("--model", action="append", help="Model id filter. Repeat to include multiple models.")
    parser.add_argument("--dataset", action="append", help="Suite dataset id filter. Repeat to include multiple datasets.")
    parser.add_argument("--io-mode", action="append", help="IO mode filter. Repeat to include multiple modes.")
    parser.add_argument("--horizon", action="append", help="Horizon id filter. Repeat to include multiple horizons.")
    parser.add_argument("--include-curation-required", action="store_true", help="Include datasets marked curation_required.")
    parser.add_argument("--dry-run", action="store_true", help="Print a JSON task summary without loading data or models.")
    parser.add_argument("--max-tasks", type=int, help="Limit the number of generated tasks to execute or summarize.")
    parser.add_argument("--device-map", default="auto", help="Device map passed to model adapters.")
    parser.add_argument("--num-windows", type=int, default=1, help="Number of chronological windows per task.")
    return parser


def _load_suite_for_cli(path: str | Path) -> dict[str, Any]:
    suite = load_suite(path)
    suite.setdefault("evaluation_modes", ["zero_shot"])
    return suite


def _run_task(task: Any, suite: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    try:
        frame = load_dataset_for_task(task, suite, data_root=args.data_root)
        windows = build_windows(frame, task, num_windows=args.num_windows)
    except DatasetUnavailableError as exc:
        return build_skipped_result(task, _skip_reason(exc.reason), str(exc))
    except InsufficientDataError as exc:
        return build_skipped_result(task, "data_unavailable", str(exc))

    try:
        adapter = get_adapter(task.model_id, device_map=args.device_map)
    except MissingDependencyError as exc:
        return build_skipped_result(task, "missing_dependency", str(exc), model_runtime=_adapter_runtime(exc))
    except UnsupportedTaskError as exc:
        return build_skipped_result(task, "unsupported_model_frequency_window", str(exc), model_runtime=_adapter_runtime(exc))

    actual_values: list[float] = []
    predicted_values: list[float] = []
    try:
        for window in windows:
            ground_truth = _target_frame(window["ground_truth"], task)
            future_df = window["ground_truth"].drop(columns=["value"])
            forecast = adapter.predict(window["context"], future_df, task)
            actual, predicted = _align_forecast(ground_truth, forecast)
            actual_values.extend(actual)
            predicted_values.extend(predicted)
        metrics = {"MAE": mae(actual_values, predicted_values)}
        runtime = {
            "adapter": adapter.__class__.__name__,
            "device_map": args.device_map,
            "num_windows": args.num_windows,
        }
        return build_completed_result(task, metrics, runtime)
    except MissingDependencyError as exc:
        return build_skipped_result(task, "missing_dependency", str(exc), model_runtime=_adapter_runtime(exc))
    except UnsupportedTaskError as exc:
        return build_skipped_result(task, "unsupported_model_frequency_window", str(exc), model_runtime=_adapter_runtime(exc))
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

    joined = ground_truth.merge(
        forecast[["item_id", "timestamp", "variable", "prediction"]],
        on=["item_id", "timestamp", "variable"],
        how="inner",
    )
    if len(joined) != len(ground_truth):
        raise ValueError("forecast does not cover every ground-truth target row")
    return joined["value"].tolist(), joined["prediction"].tolist()


def _write_cli_result(result: dict[str, Any], output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    result_path = output_path / f"{result['run_id']}.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result_path


def _skip_reason(reason: str) -> str:
    allowed = {"missing_dependency", "unsupported_model_frequency_window", "curation_required", "data_unavailable"}
    return reason if reason in allowed else "data_unavailable"


def _adapter_runtime(exc: Exception) -> dict[str, Any]:
    runtime: dict[str, Any] = {}
    for attr in ("model_id", "packages", "source_url", "reason"):
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
