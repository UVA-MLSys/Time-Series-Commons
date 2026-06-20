"""Result schema builders and JSON writer for benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .metadata import BenchmarkTask


DEFAULT_OUTPUT_DIR = Path("data/benchmark/runs")
SKIP_REASONS = {
    "missing_dependency",
    "unsupported_model_frequency_window",
    "unsupported_api_version",
    "unsupported_frequency",
    "unsupported_multitarget",
    "unsupported_runtime_api",
    "unsupported_window",
    "resource_budget_exceeded",
    "curation_required",
    "data_unavailable",
}


def build_completed_result(
    task: BenchmarkTask,
    metrics: dict[str, float],
    model_runtime: dict[str, Any],
    source_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    if task.evaluation_mode != "zero_shot":
        raise ValueError("Paper 1 results must use evaluation_mode='zero_shot'")
    if "MAE" not in metrics:
        raise ValueError("completed results require an MAE score")

    result = _base_result(task, model_runtime=model_runtime)
    result.update(
        {
            "metric": "MAE",
            "score": _jsonable_float(metrics["MAE"]),
            "secondary_metrics": {
                name: _jsonable_float(value)
                for name, value in sorted(metrics.items())
                if name != "MAE"
            },
            "status": "completed",
        }
    )
    if source_versions is not None:
        result["source_versions"] = dict(source_versions)
    return result


def build_skipped_result(
    task: BenchmarkTask,
    reason: str,
    message: str,
    model_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if reason not in SKIP_REASONS:
        raise ValueError(f"Unknown skipped result reason: {reason}")

    result = _base_result(task, model_runtime=model_runtime or {})
    result.update(
        {
            "status": "skipped",
            "error": {"reason": reason, "message": message},
        }
    )
    return result


def build_failed_result(
    task: BenchmarkTask,
    reason: str,
    message: str,
    model_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _base_result(task, model_runtime=model_runtime or {})
    result.update(
        {
            "status": "failed",
            "error": {"reason": reason, "message": message},
        }
    )
    return result


def write_result(
    result: dict[str, Any],
    output_dir: str | Path | None = None,
) -> Path:
    base_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    suite_dir = base_dir / result["benchmark_suite_id"]
    suite_dir.mkdir(parents=True, exist_ok=True)

    output_path = suite_dir / f"{result['run_id']}.json"
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return output_path.resolve()


def _base_result(
    task: BenchmarkTask,
    *,
    model_runtime: dict[str, Any],
) -> dict[str, Any]:
    if task.evaluation_mode != "zero_shot":
        raise ValueError("Paper 1 results must use evaluation_mode='zero_shot'")

    return {
        "schema_version": "0.1.0",
        "benchmark_suite_id": task.benchmark_suite_id,
        "run_id": task.run_id,
        "dataset_id": task.suite_dataset_id,
        "benchmark_id": task.benchmark_id,
        "tsc_dataset_id": task.tsc_dataset_id,
        "model_id": task.model_id,
        "io_mode": task.io_mode,
        "evaluation_mode": task.evaluation_mode,
        "horizon_id": task.horizon_id,
        "lookback_window": task.lookback_window,
        "forecast_horizon": task.forecast_horizon,
        "metric": "MAE",
        "score": None,
        "higher_is_better": False,
        "secondary_metrics": {},
        "status": None,
        "error": None,
        "model_runtime": dict(model_runtime),
        "features": {
            "observed_streams": list(task.observed_streams),
            "target_streams": list(task.target_streams),
            "known_covariates": list(task.known_covariates),
            "curation_required": task.curation_required,
        },
    }


def _jsonable_float(value: float) -> float:
    numeric = float(value)
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        raise ValueError("metric values must be finite")
    return numeric
