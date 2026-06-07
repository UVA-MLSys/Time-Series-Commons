"""Metadata loading and task generation for benchmark suites."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class BenchmarkTask:
    benchmark_suite_id: str
    suite_dataset_id: str
    tsc_dataset_id: str
    model_id: str
    io_mode: str
    evaluation_mode: str
    horizon_id: str
    lookback_window: int
    forecast_horizon: int
    observed_streams: list[str]
    target_streams: list[str]
    known_covariates: list[str]
    curation_required: bool
    benchmark_id: str | None = None

    @property
    def run_id(self) -> str:
        return (
            f"{self.benchmark_suite_id}__{self.suite_dataset_id}__"
            f"{self.model_id}__{self.io_mode}__{self.horizon_id}__zero_shot"
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["run_id"] = self.run_id
        return data


def load_suite(path: str | Path) -> dict[str, Any]:
    """Load a benchmark suite JSON document."""

    return json.loads(Path(path).read_text())


def generate_tasks(
    suite: dict[str, Any],
    include_curation_required: bool = False,
    dataset_ids: Iterable[str] | None = None,
    model_ids: Iterable[str] | None = None,
    io_modes: Iterable[str] | None = None,
    horizons: Iterable[str] | None = None,
) -> list[BenchmarkTask]:
    """Generate deterministic zero-shot benchmark tasks from suite metadata."""

    _validate_zero_shot_only(suite)

    datasets = list(suite.get("datasets", []))
    models = list(suite.get("models", []))
    window_rules = dict(suite.get("window_rules", {}))

    dataset_filter = _normalize_filter("dataset_id", dataset_ids, _dataset_ids(datasets))
    model_filter = _normalize_filter("model_id", model_ids, models)
    io_mode_filter = _normalize_filter("io_mode", io_modes, _io_modes(datasets))
    horizon_filter = _normalize_filter("horizon", horizons, _horizons(window_rules))

    tasks: list[BenchmarkTask] = []
    for dataset in datasets:
        suite_dataset_id = dataset["suite_dataset_id"]
        if dataset_filter is not None and suite_dataset_id not in dataset_filter:
            continue

        curation_required = bool(dataset.get("curation_required", False))
        if curation_required and not include_curation_required:
            continue

        frequency_rule = dataset["frequency_rule"]
        frequency_windows = window_rules.get(frequency_rule)
        if not frequency_windows:
            raise ValueError(f"Unknown frequency_rule for dataset {suite_dataset_id}: {frequency_rule}")

        for model_id in models:
            if model_filter is not None and model_id not in model_filter:
                continue
            for io_mode in dataset.get("io_modes", []):
                if io_mode_filter is not None and io_mode not in io_mode_filter:
                    continue
                for horizon_id, window in frequency_windows.items():
                    if horizon_filter is not None and horizon_id not in horizon_filter:
                        continue
                    tasks.append(
                        BenchmarkTask(
                            benchmark_suite_id=suite["benchmark_suite_id"],
                            suite_dataset_id=suite_dataset_id,
                            tsc_dataset_id=dataset["tsc_dataset_id"],
                            model_id=model_id,
                            io_mode=io_mode,
                            evaluation_mode="zero_shot",
                            horizon_id=horizon_id,
                            lookback_window=int(window["lookback_window"]),
                            forecast_horizon=int(window["forecast_horizon"]),
                            observed_streams=list(dataset.get("observed_streams", [])),
                            target_streams=list(dataset.get("target_streams", [])),
                            known_covariates=list(dataset.get("known_covariates", [])),
                            curation_required=curation_required,
                            benchmark_id=dataset.get("benchmark_id"),
                        )
                    )
    return tasks


def _validate_zero_shot_only(suite: dict[str, Any]) -> None:
    evaluation_modes = suite.get("evaluation_modes", [])
    if evaluation_modes != ["zero_shot"]:
        raise ValueError(
            "Benchmark task generation supports zero_shot suites only; "
            f"got evaluation_modes={evaluation_modes!r}"
        )


def _normalize_filter(
    label: str,
    requested: Iterable[str] | None,
    allowed: Iterable[str],
) -> set[str] | None:
    if requested is None:
        return None

    requested_set = set(requested)
    allowed_set = set(allowed)
    unknown = sorted(requested_set - allowed_set)
    if unknown:
        raise ValueError(f"Unknown {label} filter value(s): {', '.join(unknown)}")
    return requested_set


def _dataset_ids(datasets: Iterable[dict[str, Any]]) -> list[str]:
    return [dataset["suite_dataset_id"] for dataset in datasets]


def _io_modes(datasets: Iterable[dict[str, Any]]) -> set[str]:
    modes: set[str] = set()
    for dataset in datasets:
        modes.update(dataset.get("io_modes", []))
    return modes


def _horizons(window_rules: dict[str, Any]) -> set[str]:
    horizon_ids: set[str] = set()
    for frequency_windows in window_rules.values():
        horizon_ids.update(frequency_windows.keys())
    return horizon_ids
