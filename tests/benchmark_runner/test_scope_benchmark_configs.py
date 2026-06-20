import json
from pathlib import Path

from tools.benchmark_runner.benchmark_registry import (
    expand_variable_selection,
    load_registry_records,
    validate_benchmark,
)
from tools.benchmark_runner.metadata import generate_tasks


CONFIG_DIR = Path("data/benchmark/configs/zero-shot")
DATASET_REGISTRY = Path("data/benchmark/dataset-metadata.json")

EXPECTED_VARIABLES = {
    "etth1_thuml": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
    "electricity_ecl_thuml": [str(index) for index in range(320)] + ["OT"],
    "traffic_thuml": [str(index) for index in range(861)] + ["OT"],
    "weather_jena_thuml": [
        "p (mbar)",
        "T (degC)",
        "Tpot (K)",
        "Tdew (degC)",
        "rh (%)",
        "VPmax (mbar)",
        "VPact (mbar)",
        "VPdef (mbar)",
        "sh (g/kg)",
        "H2OC (mmol/mol)",
        "rho (g/m**3)",
        "wv (m/s)",
        "max. wv (m/s)",
        "wd (deg)",
        "rain (mm)",
        "raining (s)",
        "SWDR (W/m2)",
        "PAR (umol/m2/s)",
        "max. PAR (umol/m2/s)",
        "Tlog (degC)",
        "OT",
    ],
    "exchange_rate_thuml": [str(index) for index in range(7)] + ["OT"],
    "ili_thuml": [
        "% WEIGHTED ILI",
        "%UNWEIGHTED ILI",
        "AGE 0-4",
        "AGE 5-24",
        "ILITOTAL",
        "NUM. OF PROVIDERS",
        "OT",
    ],
    "m4_hourly_thuml": ["y"],
    "m4_daily_thuml": ["y"],
    "m4_monthly_thuml": ["y"],
}


def test_zero_shot_scope_configs_cover_all_available_dataset_io_mode_groups():
    paths = sorted(CONFIG_DIR.glob("*.json"))

    assert len(paths) == 20
    assert {path.stem for path in paths} >= {
        "etth1-uv-uv",
        "etth1-mv-uv",
        "etth1-mv-mv",
        "ecl-mv-mv",
        "traffic-mv-mv",
        "weather-mv-mv",
        "exchange-mv-mv",
        "m4-hourly-uv-uv",
        "m4-daily-uv-uv",
        "m4-monthly-uv-uv",
        "ili-uv-uv",
        "ili-mv-uv",
    }

    for path in paths:
        benchmark = json.loads(path.read_text(encoding="utf-8"))
        validate_benchmark(benchmark)
        tasks = generate_tasks(benchmark)
        assert len(benchmark["runs"]) == 1
        assert len(tasks) == 9
        assert {task.model_id for task in tasks} == {
            "Chronos-2",
            "TTM-R3-FT",
            "Moirai2",
        }
        assert {task.horizon_id for task in tasks} == {
            "short",
            "medium",
            "long",
        }
        assert benchmark["results"] == {}


def test_scoped_dataset_registry_declares_expected_canonical_variables():
    records = {
        record["benchmark_id"]: record
        for record in json.loads(DATASET_REGISTRY.read_text(encoding="utf-8"))["datasets"]
        if record.get("benchmark_id") in EXPECTED_VARIABLES
    }

    assert set(records) == set(EXPECTED_VARIABLES)
    for dataset_id, expected_variables in EXPECTED_VARIABLES.items():
        schema = records[dataset_id]["canonical_schema"]
        assert schema["format"] == "long_dataframe"
        assert schema["index_columns"] == ["item_id", "timestamp"]
        assert schema["variable_column"] == "variable"
        assert schema["value_column"] == "value"
        assert schema["variables"] == expected_variables
        assert schema["target_variable"] == expected_variables[-1]


def test_benchmark_variable_selections_match_dataset_registry_schema():
    for path in sorted(CONFIG_DIR.glob("*.json")):
        benchmark = json.loads(path.read_text(encoding="utf-8"))
        datasets, _models = load_registry_records(benchmark)
        run = benchmark["runs"][0]
        schema = datasets[run["dataset_id"]]["canonical_schema"]
        declared_variables = schema["variables"]
        selected_targets = expand_variable_selection(run["variables"]["targets"])
        selected_observed = expand_variable_selection(run["variables"]["observed"])

        assert selected_targets
        assert set(selected_targets).issubset(declared_variables), path.name
        assert set(selected_observed).issubset(declared_variables), path.name

        if run["io_mode"] == "UV-UV":
            assert selected_targets == [schema["target_variable"]]
            assert selected_observed == selected_targets
        elif run["io_mode"] == "MV-UV":
            assert selected_targets == [schema["target_variable"]]
            assert selected_observed == declared_variables
        elif run["io_mode"] == "MV-MV":
            assert selected_targets == declared_variables
            assert selected_observed == declared_variables
        else:
            raise AssertionError(f"unexpected IO mode: {run['io_mode']}")
