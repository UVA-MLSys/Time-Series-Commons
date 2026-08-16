"""Generate Gift-Eval faithful zero-shot benchmark registries."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


CORE_MODELS = [
    "Chronos-2",
    "Moirai2",
    "TimesFM-2.5",
    "Toto-2",
    "Granite-FlowState",
    "PatchTST-FM",
]
MODEL_PROFILES = {model_id: "default" for model_id in CORE_MODELS}
REGISTRY_PATHS = {
    "datasets": "data/benchmark/dataset-metadata.json",
    "models": "data/benchmark/model-registry.json",
}
METRICS = ["MAE", "MSE", "RMSE"]

TEST_SPLIT = 0.1
MAX_WINDOWS = 20
TERM_MULTIPLIERS = {"short": 1, "medium": 10, "long": 15}
PRED_LENGTH_BY_FREQ = {
    "monthly": 12,
    "weekly": 8,
    "daily": 30,
    "hourly": 48,
    "ten_minute": 48,
    "fifteen_minute": 48,
    "five_minute": 48,
    "ten_second": 60,
}
M4_PRED_LENGTH_BY_FREQ = {
    "yearly": 6,
    "quarterly": 8,
    "monthly": 18,
    "weekly": 13,
    "daily": 14,
    "hourly": 48,
}
FREQUENCY_CODES = {
    "monthly": "M",
    "weekly": "W",
    "daily": "D",
    "hourly": "H",
    "ten_minute": "10T",
    "fifteen_minute": "15T",
    "five_minute": "5T",
    "ten_second": "10S",
}
GIFT_EVAL_M4_IDS = {"m4_hourly_thuml", "m4_daily_thuml", "m4_monthly_thuml"}
GIFT_EVAL_MED_LONG_CONFIGS = {
    "electricity/H",
    "solar/10T",
    "kdd_cup_2018_with_missing/H",
    "LOOP_SEATTLE/5T",
    "SZ_TAXI/15T",
    "ett1/H",
    "ett2/H",
    "jena_weather/10T",
    "bizitobs_application",
    "bizitobs_service",
    "bizitobs_l2c/5T",
}
CONFIG_SLUGS = {
    "electricity_ecl_thuml": "ecl",
    "etth1_thuml": "etth1",
    "m4_daily_thuml": "m4-daily",
    "m4_hourly_thuml": "m4-hourly",
    "m4_monthly_thuml": "m4-monthly",
    "weather_jena_thuml": "weather",
    "temperature_rain_monash": "temperature-rain",
    "kdd_cup_2018_monash": "kdd-cup-2018",
    "us_births_monash": "us-births",
    "saugeenday_monash": "saugeenday",
    "covid_deaths_monash": "covid-deaths",
    "bizitobs_application_gifteval": "bizitobs-application",
    "bizitobs_service_gifteval": "bizitobs-service",
    "bizitobs_l2c_gifteval": "bizitobs-l2c",
    "ett2_gifteval": "ett2",
    "solar_gifteval": "solar",
    "hospital_gifteval": "hospital",
    "car_parts_with_missing_gifteval": "car-parts-with-missing",
    "restaurant_gifteval": "restaurant",
    "hierarchical_sales_gifteval": "hierarchical-sales",
    "loop_seattle_gifteval": "loop-seattle",
    "sz_taxi_gifteval": "sz-taxi",
}


def gift_eval_config_names(registry_path: str | Path = "data/benchmark/dataset-metadata.json") -> tuple[str, ...]:
    """Return deterministic registry filenames for Gift-Eval datasets in metadata."""

    records = _gift_eval_records(_load_dataset_records(registry_path))
    return tuple(f"{_slug(record)}-uv-uv.json" for record in records)


def build_configs(registry_path: str | Path = "data/benchmark/dataset-metadata.json") -> dict[str, dict[str, Any]]:
    """Build one UV-UV Gift-Eval registry per runnable metadata dataset."""

    configs: dict[str, dict[str, Any]] = {}
    for record in _gift_eval_records(_load_dataset_records(registry_path)):
        slug = _slug(record)
        configs[f"{slug}-uv-uv"] = _benchmark_document(record, slug=slug)
    return configs


def write_configs(
    output_dir: str | Path,
    *,
    registry_path: str | Path = "data/benchmark/dataset-metadata.json",
) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, config in sorted(build_configs(registry_path).items()):
        path = destination / f"{name}.json"
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _load_dataset_records(registry_path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(registry_path).read_text(encoding="utf-8"))["datasets"]


def _gift_eval_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        record
        for record in records
        if record.get("benchmark_ready", False)
        and (
            record.get("source", {}).get("repo_id") == "Salesforce/GiftEval"
            or record.get("benchmark_id") in GIFT_EVAL_M4_IDS
        )
        and record.get("benchmark_id") in CONFIG_SLUGS
    ]
    return sorted(selected, key=lambda record: _slug(record))


def _benchmark_document(record: dict[str, Any], *, slug: str) -> dict[str, Any]:
    benchmark_id = record["benchmark_id"]
    variables = [str(variable) for variable in record["canonical_schema"]["variables"]]
    if not variables:
        raise ValueError(f"{benchmark_id} has no canonical variables")
    window_profile_id, window_profile = _window_profile(record, slug=slug)
    run_group_id = f"{slug}-uv-uv"
    run: dict[str, Any] = {
        "run_group_id": run_group_id,
        "dataset_id": benchmark_id,
        "models": list(CORE_MODELS),
        "io_mode": "UV-UV",
        "variables": {
            "targets": variables,
            "observed": variables,
            "exogenous_streams": [],
        },
        "window_profile": window_profile_id,
        "metrics": list(METRICS),
        "evaluation_windows": list(window_profile),
    }
    if len(variables) > 1:
        run["target_policy"] = "gift_eval_univariate"
    return {
        "schema_version": "0.2.0",
        "benchmark_id": f"zero-shot-gifteval-{run_group_id}-v1",
        "evaluation_mode": "zero_shot",
        "description": f"Gift-Eval zero-shot UV-UV benchmark for {benchmark_id}.",
        "registry_paths": dict(REGISTRY_PATHS),
        "model_profiles": dict(MODEL_PROFILES),
        "window_profiles": {
            window_profile_id: window_profile,
        },
        "runs": [run],
        "results": {},
    }


def _window_profile(record: dict[str, Any], *, slug: str) -> tuple[str, dict[str, Any]]:
    benchmark_id = str(record["benchmark_id"])
    frequency = str(record.get("agent_facets", {}).get("frequency", ""))
    if not frequency:
        raise ValueError(f"{benchmark_id} has no agent_facets.frequency")
    is_m4 = benchmark_id in GIFT_EVAL_M4_IDS
    base_map = M4_PRED_LENGTH_BY_FREQ if is_m4 else PRED_LENGTH_BY_FREQ
    if frequency not in base_map:
        raise ValueError(f"{benchmark_id} has unsupported Gift-Eval frequency: {frequency}")

    base_prediction_length = base_map[frequency]
    frequency_code = FREQUENCY_CODES[frequency]
    source_config = str(record.get("source", {}).get("files", {}).get("data", ""))
    if not source_config:
        raise ValueError(f"{benchmark_id} has no source.files.data Gift-Eval config")
    terms = ("short",) if is_m4 or source_config not in GIFT_EVAL_MED_LONG_CONFIGS else tuple(TERM_MULTIPLIERS)
    profile_id = f"gift_eval_{_identifier(slug)}_{_identifier(frequency_code)}"
    windows: dict[str, Any] = {}
    for term in terms:
        multiplier = TERM_MULTIPLIERS[term]
        horizon = base_prediction_length * multiplier
        window_id = f"{profile_id}_pl{horizon}"
        windows[window_id] = {
            "forecast_horizon": horizon,
            "context_policy": "full_history",
            "num_windows_policy": "gift_eval_m4" if is_m4 else "gift_eval",
            "source_benchmark": "gift_eval",
            "source_dataset_config": f"{source_config}/{term}",
            "frequency": frequency_code,
            "term": term,
            "metadata": {
                "base_prediction_length": base_prediction_length,
                "term_multiplier": multiplier,
                "test_split_fraction": TEST_SPLIT,
                "max_windows": MAX_WINDOWS,
                "window_distance": horizon,
                "context_window": "all available history before each rolling forecast cutoff",
                "window_count_rule": (
                    "1 for M4 datasets"
                    if is_m4
                    else "ceil(0.1 * shortest_series_length / forecast_horizon), clipped to [1, 20]"
                ),
                "aggregation": "score over all target points from all rolling windows",
            },
        }
    return profile_id, windows


def _slug(record: dict[str, Any]) -> str:
    benchmark_id = str(record["benchmark_id"])
    return CONFIG_SLUGS.get(benchmark_id, _identifier(record["dataset_id"]).replace("_", "-"))


def _identifier(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return text or "dataset"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/benchmark/configs/zero-shot")
    parser.add_argument("--registry-path", default="data/benchmark/dataset-metadata.json")
    args = parser.parse_args()
    for path in write_configs(args.output_dir, registry_path=args.registry_path):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
