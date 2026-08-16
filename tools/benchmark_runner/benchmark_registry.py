"""Validation and persistence for combined benchmark specification/result files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


DEFAULT_DATASET_REGISTRY = Path("data/benchmark/dataset-metadata.json")
DEFAULT_MODEL_REGISTRY = Path("data/benchmark/model-registry.json")


def load_registry_records(
    benchmark: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    paths = benchmark.get("registry_paths", {})
    dataset_path = Path(paths.get("datasets", DEFAULT_DATASET_REGISTRY))
    model_path = Path(paths.get("models", DEFAULT_MODEL_REGISTRY))

    datasets = json.loads(dataset_path.read_text(encoding="utf-8"))["datasets"]
    models = json.loads(model_path.read_text(encoding="utf-8"))["models"]
    return (
        _dataset_index(datasets),
        _model_index(models),
    )


def validate_benchmark(benchmark: dict[str, Any]) -> None:
    if benchmark.get("schema_version") != "0.2.0":
        raise ValueError("Combined benchmark registries require schema_version='0.2.0'")
    if benchmark.get("evaluation_mode") != "zero_shot":
        raise ValueError("This runner currently supports evaluation_mode='zero_shot' only")
    if not benchmark.get("benchmark_id"):
        raise ValueError("Benchmark registry must define benchmark_id")

    datasets, models = load_registry_records(benchmark)
    windows = _window_definitions(benchmark)
    model_profiles = benchmark.get("model_profiles", {})
    seen_run_groups: set[str] = set()

    for run in benchmark.get("runs", []):
        run_group_id = run.get("run_group_id")
        if not run_group_id:
            raise ValueError("Every benchmark run group must define run_group_id")
        if run_group_id in seen_run_groups:
            raise ValueError(f"Duplicate run_group_id: {run_group_id}")
        seen_run_groups.add(run_group_id)

        dataset_id = run.get("dataset_id")
        if dataset_id not in datasets:
            raise ValueError(f"Unknown benchmark dataset: {dataset_id}")
        dataset_modes = set(datasets[dataset_id].get("capabilities", {}).get("io_modes", []))
        io_mode = run.get("io_mode")
        if io_mode not in dataset_modes:
            raise ValueError(f"Dataset {dataset_id} does not support io_mode={io_mode}")

        selected_windows = set(run.get("evaluation_windows", run.get("horizons", [])))
        unknown_windows = selected_windows - set(windows)
        if unknown_windows:
            raise ValueError(
                f"Unknown evaluation window(s) for {run_group_id}: {', '.join(sorted(unknown_windows))}"
            )
        for window_id in selected_windows:
            _validate_window_definition(run_group_id, window_id, windows[window_id])

        variables = run.get("variables", {})
        _validate_variable_roles(run_group_id, io_mode, variables, run)
        _validate_dataset_variables(run_group_id, datasets[dataset_id], variables)

        for model_id in run.get("models", []):
            if model_id not in models:
                raise ValueError(f"Unknown model in {run_group_id}: {model_id}")
            model = models[model_id]
            if "zero_shot" not in model.get("evaluation_modes", []):
                raise ValueError(f"Model {model_id} does not support zero_shot evaluation")
            if io_mode not in model.get("io_modes", []):
                raise ValueError(f"Model {model_id} does not support io_mode={io_mode}")
            profile = model_profiles.get(model_id)
            if not profile:
                raise ValueError(f"No model profile selected for {model_id}")
            if profile not in model.get("profiles", {}):
                raise ValueError(f"Unknown profile for {model_id}: {profile}")


def resolve_model_profile(
    benchmark: dict[str, Any],
    model_id: str,
    profile_name: str,
) -> dict[str, Any]:
    _, models = load_registry_records(benchmark)
    try:
        profile = models[model_id]["profiles"][profile_name]
    except KeyError as exc:
        raise ValueError(f"Unknown model profile: {model_id}={profile_name}") from exc
    return dict(profile)


def _window_definitions(benchmark: dict[str, Any]) -> dict[str, Any]:
    if "windows" in benchmark:
        return dict(benchmark.get("windows") or {})
    windows: dict[str, Any] = {}
    for profile in (benchmark.get("window_profiles") or {}).values():
        if isinstance(profile, dict):
            windows.update(profile)
    return windows


def expand_variable_selection(selection: Any) -> list[str]:
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


def record_result(path: str | Path, result: dict[str, Any]) -> None:
    """Append an attempt and atomically update the result ledger in-place."""

    benchmark_path = Path(path)
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    results = benchmark.setdefault("results", {})
    run_id = result["run_id"]
    previous = results.get(run_id, {})
    attempts = list(previous.get("attempts", []))

    attempt = {
        "attempt": len(attempts) + 1,
        "status": result["status"],
    }
    for key in (
        "started_at",
        "completed_at",
        "metrics",
        "forecast_artifact",
        "error",
        "runtime",
        "model_runtime",
    ):
        if key in result and result[key] is not None:
            attempt[key] = result[key]
    attempts.append(attempt)

    stored = {key: value for key, value in result.items() if key != "run_id"}
    stored["attempts"] = attempts
    results[run_id] = stored
    _atomic_write_json(benchmark_path, benchmark)


def _validate_variable_roles(
    run_group_id: str,
    io_mode: str,
    variables: dict[str, Any],
    run: dict[str, Any] | None = None,
) -> None:
    targets = expand_variable_selection(variables.get("targets", []))
    observed = expand_variable_selection(variables.get("observed", []))
    exogenous_streams = expand_variable_selection(
        variables.get("exogenous_streams", variables.get("known_future", []))
    )
    if not targets or not observed:
        raise ValueError(f"{run_group_id} must define target and observed variables")
    if not set(targets).issubset(observed):
        raise ValueError(f"{run_group_id} targets must be included in observed variables")
    if not set(exogenous_streams).issubset(observed):
        raise ValueError(f"{run_group_id} exogenous_streams variables must be observed")
    target_policy = (run or {}).get("target_policy")
    if io_mode == "UV-UV":
        gift_eval_univariate = target_policy == "gift_eval_univariate"
        if observed != targets:
            raise ValueError(f"{run_group_id} UV-UV requires identical observed/target variables")
        if len(targets) != 1 and not gift_eval_univariate:
            raise ValueError(f"{run_group_id} UV-UV requires one target variable")
    if io_mode == "MV-UV" and (len(targets) != 1 or len(observed) < 2):
        raise ValueError(f"{run_group_id} MV-UV requires one target and multiple observed variables")
    if io_mode == "MV-MV" and (len(targets) < 2 or set(targets) != set(observed)):
        raise ValueError(f"{run_group_id} MV-MV requires multiple jointly observed targets")


def _validate_dataset_variables(
    run_group_id: str,
    dataset: dict[str, Any],
    variables: dict[str, Any],
) -> None:
    declared = dataset.get("canonical_schema", {}).get("variables")
    if not declared:
        raise ValueError(
            f"Dataset {dataset.get('benchmark_id')} does not declare canonical variables"
        )

    declared_set = set(str(variable) for variable in declared)
    selected = {
        *expand_variable_selection(variables.get("targets", [])),
        *expand_variable_selection(variables.get("observed", [])),
        *expand_variable_selection(
            variables.get("exogenous_streams", variables.get("known_future", []))
        ),
    }
    unknown = sorted(selected - declared_set)
    if unknown:
        raise ValueError(
            f"{run_group_id} selects unknown dataset variable(s): {', '.join(unknown)}"
        )


def _validate_window_definition(
    run_group_id: str,
    window_id: str,
    window: dict[str, Any],
) -> None:
    if "forecast_horizon" not in window:
        raise ValueError(f"{run_group_id} window {window_id} must define forecast_horizon")
    if int(window["forecast_horizon"]) < 1:
        raise ValueError(f"{run_group_id} window {window_id} forecast_horizon must be positive")

    context_policy = window.get("context_policy", "fixed_length")
    if context_policy == "fixed_length" and "lookback_window" not in window:
        raise ValueError(f"{run_group_id} window {window_id} must define lookback_window")
    if context_policy == "full_history" and window.get("lookback_window") is not None:
        raise ValueError(f"{run_group_id} window {window_id} should not define fixed lookback_window")
    if context_policy not in {"fixed_length", "full_history"}:
        raise ValueError(f"{run_group_id} window {window_id} has unknown context_policy={context_policy!r}")


def _unique_index(
    records: list[dict[str, Any]],
    key: str,
    *,
    fallback_key: str | None = None,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        value = record.get(key)
        if value is None and fallback_key is not None:
            value = record.get(fallback_key)
        if value is None:
            continue
        if value in index:
            raise ValueError(f"Registry key is ambiguous: {key}={value}")
        index[str(value)] = record
    return index


def _dataset_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        benchmark_id = record.get("benchmark_id")
        if benchmark_id is None:
            continue
        if benchmark_id in index:
            raise ValueError(f"Registry key is ambiguous: benchmark_id={benchmark_id}")
        index[str(benchmark_id)] = record

    for record in records:
        if record.get("benchmark_id") is not None:
            continue
        dataset_id = record.get("dataset_id")
        if dataset_id is not None:
            index.setdefault(str(dataset_id), record)
    return index


def _model_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index model records from either benchmark or website registry shape."""

    index: dict[str, dict[str, Any]] = {}
    for record in records:
        normalized = _normalize_model_record(record)
        model_id = normalized["model_id"]
        if model_id in index:
            raise ValueError(f"Duplicate model_id in registry: {model_id}")
        index[model_id] = normalized
    return index


def _normalize_model_record(record: dict[str, Any]) -> dict[str, Any]:
    model_id = record.get("model_id") or record.get("name") or record.get("id")
    if not model_id:
        raise ValueError(f"Model record missing model_id/name/id: {record}")

    normalized = dict(record)
    normalized["model_id"] = str(model_id)
    normalized.setdefault("model_type", record.get("type"))
    normalized.setdefault("evaluation_modes", record.get("evaluationModes", []))
    normalized.setdefault("io_modes", record.get("ioModes", []))
    normalized.setdefault("source_link", record.get("sourceLink", ""))
    normalized.setdefault("runtime_package", record.get("runtimePackage"))
    normalized.setdefault("agent_facets", record.get("agentFacets", {}))
    normalized.setdefault("profiles", record.get("profiles", {}))
    return normalized


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(data, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)
