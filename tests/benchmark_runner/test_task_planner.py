import json

import pytest

from tools.benchmark_runner.metadata import generate_tasks, load_suite


def paper1_suite():
    return {
        "benchmark_suite_id": "paper1-v0",
        "models": ["Chronos-2", "TTM-R3-FT", "Moirai2"],
        "evaluation_modes": ["zero_shot"],
        "window_rules": {
            "hourly": {
                "short": {"lookback_window": 72, "forecast_horizon": 24},
                "medium": {"lookback_window": 336, "forecast_horizon": 168},
                "long": {"lookback_window": 720, "forecast_horizon": 720},
            },
            "monthly": {
                "short": {"lookback_window": 24, "forecast_horizon": 6},
            },
        },
        "datasets": [
            {
                "suite_dataset_id": "paper1_etth1",
                "tsc_dataset_id": "ett-hourly-station-1-etth1",
                "frequency_rule": "hourly",
                "io_modes": ["UV-UV", "MV-UV", "MV-MV"],
                "target_streams": ["OT"],
                "observed_streams": ["HUFL", "OT"],
            },
            {
                "suite_dataset_id": "paper1_m4_monthly",
                "tsc_dataset_id": "m4-monthly",
                "frequency_rule": "monthly",
                "io_modes": ["UV-UV"],
                "target_streams": ["y"],
                "observed_streams": ["y"],
            },
            {
                "suite_dataset_id": "paper1_traffic",
                "tsc_dataset_id": "traffic-dataset",
                "frequency_rule": "hourly",
                "io_modes": ["UV-UV", "MV-UV", "MV-MV"],
                "target_streams": ["OT"],
                "observed_streams": ["sensor_1", "OT"],
                "curation_required": True,
            },
        ],
    }


def test_load_suite_reads_json_file(tmp_path):
    suite_path = tmp_path / "paper1-suite.json"
    suite_path.write_text(json.dumps(paper1_suite()))

    assert load_suite(suite_path)["benchmark_suite_id"] == "paper1-v0"


def test_generate_tasks_keeps_m4_univariate_only():
    tasks = generate_tasks(
        paper1_suite(),
        dataset_ids=["paper1_m4_monthly"],
        model_ids=["Chronos-2"],
    )

    assert {task.io_mode for task in tasks} == {"UV-UV"}
    assert all(task.run_id.endswith("__zero_shot") for task in tasks)


def test_generate_tasks_includes_all_etth1_io_modes_and_zero_shot_only():
    tasks = generate_tasks(
        paper1_suite(),
        dataset_ids=["paper1_etth1"],
        model_ids=["Chronos-2"],
        horizons=["short"],
    )

    assert {task.io_mode for task in tasks} == {"UV-UV", "MV-UV", "MV-MV"}
    assert {task.evaluation_mode for task in tasks} == {"zero_shot"}
    assert {
        task.run_id
        for task in tasks
    } == {
        "paper1-v0__paper1_etth1__Chronos-2__UV-UV__short__zero_shot",
        "paper1-v0__paper1_etth1__Chronos-2__MV-UV__short__zero_shot",
        "paper1-v0__paper1_etth1__Chronos-2__MV-MV__short__zero_shot",
    }


def test_generate_tasks_uses_hourly_short_medium_long_windows():
    tasks = generate_tasks(
        paper1_suite(),
        dataset_ids=["paper1_etth1"],
        model_ids=["Chronos-2"],
        io_modes=["UV-UV"],
    )

    windows = {
        task.horizon_id: (task.lookback_window, task.forecast_horizon)
        for task in tasks
    }
    assert windows == {
        "short": (72, 24),
        "medium": (336, 168),
        "long": (720, 720),
    }


def test_generate_tasks_filters_curation_required_by_default():
    tasks = generate_tasks(paper1_suite(), dataset_ids=["paper1_traffic"])

    assert tasks == []


def test_generate_tasks_can_include_curation_required_tasks():
    tasks = generate_tasks(
        paper1_suite(),
        include_curation_required=True,
        dataset_ids=["paper1_traffic"],
        model_ids=["Chronos-2"],
        io_modes=["MV-MV"],
        horizons=["short"],
    )

    assert len(tasks) == 1
    assert tasks[0].curation_required is True


@pytest.mark.parametrize(
    ("filter_name", "filters"),
    [
        ("dataset_id", {"dataset_ids": ["missing_dataset"]}),
        ("model_id", {"model_ids": ["MissingModel"]}),
        ("io_mode", {"io_modes": ["missing_mode"]}),
        ("horizon", {"horizons": ["missing_horizon"]}),
    ],
)
def test_generate_tasks_rejects_unknown_filters(filter_name, filters):
    with pytest.raises(ValueError, match=filter_name):
        generate_tasks(paper1_suite(), **filters)
