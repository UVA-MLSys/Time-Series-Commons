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
    lookback_window: int | None
    forecast_horizon: int
    observed_streams: list[str]
    target_streams: list[str]
    known_covariates: list[str]
    curation_required: bool
    benchmark_id: str | None = None
    run_group_id: str | None = None
    model_profile: str | None = None
    metrics: list[str] | None = None
    num_windows: int | None = None
    num_windows_policy: str | None = None
    frequency: str | None = None
    window_id: str | None = None
    context_policy: str = "fixed_length"
    source_benchmark: str | None = None
    source_dataset_config: str | None = None
    window_metadata: dict[str, Any] | None = None

    @property
    def run_id(self) -> str:
        window_id = self.window_id or self.horizon_id
        if self.run_group_id:
            return f"{self.run_group_id}__{self.model_id}__{window_id}"
        return (
            f"{self.benchmark_suite_id}__{self.suite_dataset_id}__"
            f"{self.model_id}__{self.io_mode}__{window_id}__zero_shot"
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
    run_group_ids: Iterable[str] | None = None,
) -> list[BenchmarkTask]:
    """Generate deterministic zero-shot benchmark tasks from suite metadata."""

    if suite.get("schema_version") == "0.2.0":
        return _generate_combined_registry_tasks(
            suite,
            run_group_ids=run_group_ids,
            model_ids=model_ids,
            io_modes=io_modes,
            horizons=horizons,
        )

    if run_group_ids is not None:
        raise ValueError("run_group_ids can only be used with combined benchmark registries")

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


def _generate_combined_registry_tasks(
    benchmark: dict[str, Any],
    *,
    run_group_ids: Iterable[str] | None = None,
    model_ids: Iterable[str] | None = None,
    io_modes: Iterable[str] | None = None,
    horizons: Iterable[str] | None = None,
) -> list[BenchmarkTask]:
    """Generate tasks from a combined benchmark registry/result file."""

    if benchmark.get("evaluation_mode") != "zero_shot":
        raise ValueError(
            "Combined benchmark task generation supports zero_shot registries only; "
            f"got evaluation_mode={benchmark.get('evaluation_mode')!r}"
        )

    runs = list(benchmark.get("runs", []))
    windows = _combined_window_definitions(benchmark)
    model_profiles = dict(benchmark.get("model_profiles", {}))

    run_group_filter = _normalize_filter("run_group_id", run_group_ids, _run_group_ids(runs))
    model_filter = _normalize_filter("model_id", model_ids, _combined_model_ids(runs))
    io_mode_filter = _normalize_filter("io_mode", io_modes, _combined_io_modes(runs))
    horizon_filter = _normalize_filter("window", horizons, _combined_horizons(runs, windows))

    tasks: list[BenchmarkTask] = []
    for run in runs:
        run_group_id = run["run_group_id"]
        if run_group_filter is not None and run_group_id not in run_group_filter:
            continue

        io_mode = run["io_mode"]
        if io_mode_filter is not None and io_mode not in io_mode_filter:
            continue

        variables = run.get("variables", {})
        observed = _expand_selection(variables.get("observed", []))
        targets = _expand_selection(variables.get("targets", []))
        exogenous_streams = _expand_selection(
            variables.get("exogenous_streams", variables.get("known_future", []))
        )

        for model_id in run.get("models", []):
            if model_filter is not None and model_id not in model_filter:
                continue
            for window_id in run.get("evaluation_windows", run.get("horizons", [])):
                if horizon_filter is not None and window_id not in horizon_filter:
                    continue
                if window_id not in windows:
                    raise ValueError(f"Unknown evaluation window for {run_group_id}: {window_id}")
                window = windows[window_id]
                legacy_horizon_id = str(window.get("term", window_id))
                lookback_window = window.get("lookback_window")
                tasks.append(
                    BenchmarkTask(
                        benchmark_suite_id=benchmark["benchmark_id"],
                        suite_dataset_id=run_group_id,
                        tsc_dataset_id=run["dataset_id"],
                        benchmark_id=run["dataset_id"],
                        model_id=model_id,
                        io_mode=io_mode,
                        evaluation_mode="zero_shot",
                        horizon_id=legacy_horizon_id,
                        window_id=window_id,
                        lookback_window=None if lookback_window is None else int(lookback_window),
                        forecast_horizon=int(window["forecast_horizon"]),
                        observed_streams=observed,
                        target_streams=targets,
                        known_covariates=exogenous_streams,
                        curation_required=False,
                        run_group_id=run_group_id,
                        model_profile=model_profiles.get(model_id),
                        metrics=list(run.get("metrics", [])),
                        num_windows=_optional_int(run.get("num_windows", window.get("num_windows"))),
                        num_windows_policy=window.get("num_windows_policy") or run.get("num_windows_policy"),
                        frequency=window.get("frequency") or run.get("window_profile"),
                        context_policy=str(window.get("context_policy", "fixed_length")),
                        source_benchmark=window.get("source_benchmark"),
                        source_dataset_config=window.get("source_dataset_config"),
                        window_metadata=dict(window.get("metadata", {})),
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


def _combined_window_definitions(benchmark: dict[str, Any]) -> dict[str, Any]:
    if "windows" in benchmark:
        return dict(benchmark.get("windows") or {})
    windows: dict[str, Any] = {}
    for profile in (benchmark.get("window_profiles") or {}).values():
        if isinstance(profile, dict):
            windows.update(profile)
    return windows


def _run_group_ids(runs: Iterable[dict[str, Any]]) -> list[str]:
    return [run["run_group_id"] for run in runs]


def _combined_model_ids(runs: Iterable[dict[str, Any]]) -> set[str]:
    model_ids: set[str] = set()
    for run in runs:
        model_ids.update(run.get("models", []))
    return model_ids


def _combined_io_modes(runs: Iterable[dict[str, Any]]) -> set[str]:
    return {run["io_mode"] for run in runs}


def _combined_horizons(
    runs: Iterable[dict[str, Any]],
    windows: dict[str, Any],
) -> set[str]:
    horizon_ids: set[str] = set()
    for run in runs:
        horizon_ids.update(run.get("evaluation_windows", run.get("horizons", [])))
    horizon_ids.update(windows)
    return horizon_ids


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _expand_selection(selection: Any) -> list[str]:
    if isinstance(selection, list):
        return [str(value) for value in selection]
    if not isinstance(selection, dict):
        raise ValueError("Variable selection must be a list or selector object")

    variables: list[str] = []
    for numeric_range in selection.get("numeric_ranges", []):
        start = int(numeric_range["start"])
        end = int(numeric_range["end"])
        if end < start:
            raise ValueError(f"Invalid numeric variable range: {start}..{end}")
        variables.extend(str(value) for value in range(start, end + 1))
    variables.extend(str(value) for value in selection.get("names", []))
    return list(dict.fromkeys(variables))
