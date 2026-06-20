import json
from pathlib import Path

import pytest

from tools.benchmark_runner.benchmark_registry import (
    expand_variable_selection,
    record_result,
    validate_benchmark,
)
from tools.benchmark_runner.metadata import generate_tasks, load_suite


EXAMPLE_PATH = Path("data/benchmark/runs/examples/example-run-result.json")


def test_combined_benchmark_registry_expands_run_groups_to_concrete_tasks():
    benchmark = load_suite(EXAMPLE_PATH)

    tasks = generate_tasks(
        benchmark,
        run_group_ids=["etth1-mv-uv"],
        model_ids=["Chronos-2"],
        horizons=["short", "long"],
    )

    assert [task.run_id for task in tasks] == [
        "etth1-mv-uv__Chronos-2__short",
        "etth1-mv-uv__Chronos-2__long",
    ]
    assert tasks[0].model_profile == "default"
    assert tasks[0].observed_streams[-1] == "OT"
    assert tasks[0].target_streams == ["OT"]
    assert tasks[0].known_covariates == []
    assert tasks[0].metrics == ["MAE", "MSE", "RMSE"]
    assert tasks[0].num_windows == 3
    assert tasks[0].frequency == "hourly"


def test_combined_benchmark_registry_validates_model_and_dataset_capabilities():
    benchmark = load_suite(EXAMPLE_PATH)

    validate_benchmark(benchmark)


def test_combined_benchmark_registry_rejects_unknown_dataset_variables():
    benchmark = load_suite(EXAMPLE_PATH)
    benchmark["runs"][0]["variables"]["observed"].append("NOT_A_REAL_VARIABLE")

    with pytest.raises(ValueError, match="NOT_A_REAL_VARIABLE"):
        validate_benchmark(benchmark)


def test_numeric_range_variable_selection_expands_to_dataset_column_names():
    assert expand_variable_selection(
        {
            "numeric_ranges": [{"start": 0, "end": 2}],
            "names": ["OT"],
        }
    ) == ["0", "1", "2", "OT"]


def test_record_result_updates_the_same_benchmark_file_and_appends_attempt(tmp_path):
    path = tmp_path / "benchmark.json"
    benchmark = load_suite(EXAMPLE_PATH)
    benchmark["results"] = {}
    path.write_text(json.dumps(benchmark), encoding="utf-8")

    result = {
        "run_id": "etth1-mv-uv__Chronos-2__short",
        "run_group_id": "etth1-mv-uv",
        "model_id": "Chronos-2",
        "status": "completed",
        "metrics": {"MAE": 0.5},
        "runtime": {"checkpoint": "amazon/chronos-2"},
        "started_at": "2026-06-07T10:00:00Z",
        "completed_at": "2026-06-07T10:00:01Z",
    }

    record_result(path, result)
    record_result(path, {**result, "metrics": {"MAE": 0.4}})

    stored = json.loads(path.read_text(encoding="utf-8"))["results"][result["run_id"]]
    assert stored["metrics"] == {"MAE": 0.4}
    assert [attempt["attempt"] for attempt in stored["attempts"]] == [1, 2]
    assert stored["attempts"][-1]["metrics"] == {"MAE": 0.4}
