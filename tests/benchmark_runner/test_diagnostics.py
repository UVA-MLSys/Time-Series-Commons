import json

from tools.benchmark_runner.diagnostics import summarize_registry_dir


def test_summarize_registry_dir_groups_failures_by_model_mode_and_error(tmp_path):
    registry = {
        "runs": [
            {
                "run_id": "paper1-v0__paper1_etth1__Chronos-2__MV-MV__short__zero_shot",
                "status": "failed",
                "model_id": "Chronos-2",
                "suite_dataset_id": "paper1_etth1",
                "io_mode": "MV-MV",
                "horizon_id": "short",
                "error": {
                    "type": "ValueError",
                    "message": "forecast does not cover every ground-truth target row",
                },
            },
            {
                "run_id": "paper1-v0__paper1_traffic__Moirai2__MV-UV__long__zero_shot",
                "status": "failed",
                "model_id": "Moirai2",
                "suite_dataset_id": "paper1_traffic",
                "io_mode": "MV-UV",
                "horizon_id": "long",
                "error": {
                    "reason": "OutOfMemoryError",
                    "message": "CUDA out of memory. Tried to allocate 11.24 GiB",
                },
            },
            {
                "run_id": "paper1-v0__paper1_weather__Moirai2__MV-MV__short__zero_shot",
                "status": "skipped",
                "model_id": "Moirai2",
                "suite_dataset_id": "paper1_weather",
                "io_mode": "MV-MV",
                "horizon_id": "short",
                "error": {
                    "reason": "data_unavailable",
                    "message": "Canonical dataset contains duplicate item_id/timestamp/variable keys",
                },
            },
        ]
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")

    summary = summarize_registry_dir(tmp_path)

    assert summary["totals"] == {"failed": 2, "skipped": 1}
    assert summary["failure_groups"] == [
        {
            "count": 1,
            "model_id": "Chronos-2",
            "io_mode": "MV-MV",
            "error_type": "ValueError",
            "message_prefix": "forecast does not cover every ground-truth target row",
        },
        {
            "count": 1,
            "model_id": "Moirai2",
            "io_mode": "MV-UV",
            "error_type": "OutOfMemoryError",
            "message_prefix": "CUDA out of memory. Tried to allocate 11.24 GiB",
        },
    ]
