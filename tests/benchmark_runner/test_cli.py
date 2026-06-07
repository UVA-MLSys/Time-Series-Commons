import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from tools.benchmark_runner import cli


def _write_suite(path: Path, data_path: str | None = None) -> None:
    dataset = {
        "suite_dataset_id": "paper1_etth1",
        "tsc_dataset_id": "ett-hourly-station-1-etth1",
        "frequency_rule": "hourly",
        "io_modes": ["UV-UV", "MV-UV"],
        "target_streams": ["OT"],
        "observed_streams": ["OT", "HUFL"],
    }
    if data_path is not None:
        dataset["path"] = data_path
    suite = {
        "benchmark_suite_id": "paper1-v0",
        "evaluation_modes": ["zero_shot"],
        "models": ["Chronos-2", "Moirai2"],
        "window_rules": {
            "hourly": {
                "short": {"lookback_window": 2, "forecast_horizon": 1},
                "medium": {"lookback_window": 3, "forecast_horizon": 1},
            }
        },
        "datasets": [
            dataset,
            {
                "suite_dataset_id": "paper1_traffic",
                "tsc_dataset_id": "traffic-dataset",
                "frequency_rule": "hourly",
                "io_modes": ["UV-UV"],
                "target_streams": ["OT"],
                "observed_streams": ["OT"],
                "curation_required": True,
            },
        ],
    }
    path.write_text(json.dumps(suite), encoding="utf-8")


def test_build_dry_run_summary_counts_tasks_by_fields():
    tasks = [
        SimpleNamespace(model_id="Chronos-2", suite_dataset_id="paper1_etth1", io_mode="UV-UV", horizon_id="short"),
        SimpleNamespace(model_id="Chronos-2", suite_dataset_id="paper1_etth1", io_mode="MV-UV", horizon_id="short"),
        SimpleNamespace(model_id="Moirai2", suite_dataset_id="paper1_etth1", io_mode="UV-UV", horizon_id="medium"),
    ]

    summary = cli.build_dry_run_summary(tasks)

    assert summary["task_count"] == 3
    assert summary["models"] == {"Chronos-2": 2, "Moirai2": 1}
    assert summary["io_modes"] == {"MV-UV": 1, "UV-UV": 2}
    assert summary["horizons"] == {"medium": 1, "short": 2}


def test_dry_run_filters_by_repeatable_options_and_prints_json(tmp_path, capsys):
    suite_path = tmp_path / "paper1-suite.json"
    _write_suite(suite_path)

    exit_code = cli.main(
        [
            "--suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "runs"),
            "--model",
            "Chronos-2",
            "--dataset",
            "paper1_etth1",
            "--io-mode",
            "UV-UV",
            "--horizon",
            "short",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["task_count"] == 1
    assert summary["models"] == {"Chronos-2": 1}
    assert summary["datasets"] == {"paper1_etth1": 1}


def test_real_run_writes_completed_result_for_selected_task(tmp_path, monkeypatch):
    data_path = tmp_path / "toy.csv"
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=4, freq="h"),
            "OT": [1.0, 2.0, 3.0, 4.0],
            "HUFL": [10.0, 11.0, 12.0, 13.0],
        }
    ).to_csv(data_path, index=False)
    suite_path = tmp_path / "paper1-suite.json"
    _write_suite(suite_path, data_path=data_path.name)

    class Adapter:
        model_id = "Chronos-2"

        def predict(self, context_df, future_df, task):
            forecast = future_df[["item_id", "timestamp", "variable"]].copy()
            forecast["prediction"] = forecast["variable"].map({"OT": 4.0, "HUFL": 13.0})
            return forecast

    monkeypatch.setattr(cli, "get_adapter", lambda model_id, device_map="auto": Adapter())

    exit_code = cli.main(
        [
            "--suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "runs"),
            "--data-root",
            str(tmp_path),
            "--model",
            "Chronos-2",
            "--dataset",
            "paper1_etth1",
            "--io-mode",
            "UV-UV",
            "--horizon",
            "short",
            "--max-tasks",
            "1",
        ]
    )

    result_files = list((tmp_path / "runs").glob("*.json"))
    assert exit_code == 0
    assert len(result_files) == 1
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["evaluation_mode"] == "zero_shot"
    assert result["score"] == 0.0


def test_real_run_writes_skipped_result_when_dataset_is_missing(tmp_path):
    suite_path = tmp_path / "paper1-suite.json"
    _write_suite(suite_path, data_path="missing.csv")

    exit_code = cli.main(
        [
            "--suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "runs"),
            "--data-root",
            str(tmp_path),
            "--max-tasks",
            "1",
        ]
    )

    result_files = list((tmp_path / "runs").glob("*.json"))
    assert exit_code == 0
    assert len(result_files) == 1
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result["status"] == "skipped"
    assert result["error"]["reason"] == "data_unavailable"


def test_real_run_writes_skipped_result_when_model_dependency_is_missing(tmp_path, monkeypatch):
    data_path = tmp_path / "toy.csv"
    pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=3, freq="h"), "OT": [1.0, 2.0, 3.0]}).to_csv(
        data_path, index=False
    )
    suite_path = tmp_path / "paper1-suite.json"
    _write_suite(suite_path, data_path=data_path.name)

    def missing_adapter(model_id, device_map="auto"):
        raise cli.MissingDependencyError("Chronos-2", ("chronos-forecasting",), "https://example.test")

    monkeypatch.setattr(cli, "get_adapter", missing_adapter)

    exit_code = cli.main(
        [
            "--suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "runs"),
            "--data-root",
            str(tmp_path),
            "--model",
            "Chronos-2",
            "--dataset",
            "paper1_etth1",
            "--io-mode",
            "UV-UV",
            "--horizon",
            "short",
            "--max-tasks",
            "1",
        ]
    )

    result = json.loads(next((tmp_path / "runs").glob("*.json")).read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["status"] == "skipped"
    assert result["error"]["reason"] == "missing_dependency"
