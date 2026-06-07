import json
import math

import pytest

from tools.benchmark_runner.metadata import BenchmarkTask
from tools.benchmark_runner.metrics import (
    mae,
    mase,
    mse,
    rmse,
    smape,
    summarize_metrics,
)
from tools.benchmark_runner.results import (
    build_completed_result,
    build_failed_result,
    build_skipped_result,
    write_result,
)


def sample_task():
    return BenchmarkTask(
        benchmark_suite_id="forecasting-v0",
        suite_dataset_id="forecast_etth1",
        tsc_dataset_id="ett-hourly-station-1-etth1",
        model_id="Chronos-2",
        io_mode="MV-UV",
        evaluation_mode="zero_shot",
        horizon_id="short",
        lookback_window=72,
        forecast_horizon=24,
        observed_streams=["HUFL", "OT"],
        target_streams=["OT"],
        known_covariates=[],
        curation_required=False,
    )


def test_point_metrics_match_expected_values():
    actual = [1.0, 2.0, 4.0]
    predicted = [1.5, 1.0, 5.0]

    assert mae(actual, predicted) == pytest.approx(5.0 / 6.0)
    assert mse(actual, predicted) == pytest.approx(0.75)
    assert rmse(actual, predicted) == pytest.approx(math.sqrt(0.75))
    assert smape(actual, predicted) == pytest.approx(
        (abs(1.5 - 1.0) / ((abs(1.0) + abs(1.5)) / 2.0)
        + abs(1.0 - 2.0) / ((abs(2.0) + abs(1.0)) / 2.0)
        + abs(5.0 - 4.0) / ((abs(4.0) + abs(5.0)) / 2.0))
        / 3.0
        * 100.0
    )


def test_mase_uses_seasonal_naive_error_from_insample_values():
    actual = [10.0, 13.0]
    predicted = [12.0, 12.0]
    insample = [1.0, 3.0, 6.0, 10.0]

    assert mase(actual, predicted, insample=insample, seasonal_period=1) == pytest.approx(0.5)


@pytest.mark.parametrize(
    "call",
    [
        lambda: mae([1.0], [1.0, 2.0]),
        lambda: mse([], []),
        lambda: smape([0.0], [0.0]),
        lambda: mase([1.0], [2.0], insample=[3.0], seasonal_period=1),
        lambda: mase([1.0], [2.0], insample=[3.0, 3.0], seasonal_period=1),
        lambda: mase([1.0], [2.0], insample=[3.0, 4.0], seasonal_period=0),
    ],
)
def test_metric_validation_raises_clear_errors(call):
    with pytest.raises(ValueError):
        call()


def test_summarize_metrics_returns_all_forecasting_metrics():
    metrics = summarize_metrics(
        [1.0, 2.0, 4.0],
        [1.5, 1.0, 5.0],
        insample=[1.0, 2.0, 3.0, 4.0],
        seasonal_period=1,
    )

    assert set(metrics) == {"MAE", "MSE", "RMSE", "sMAPE", "MASE"}


def test_completed_result_schema_uses_mae_as_primary_score():
    result = build_completed_result(
        sample_task(),
        {"MAE": 0.5, "MSE": 0.25, "RMSE": 0.5, "sMAPE": 10.0, "MASE": 0.25},
        model_runtime={"package": "chronos-forecasting"},
        source_versions={"chronos-forecasting": "x.y.z"},
    )

    assert result["run_id"] == sample_task().run_id
    assert result["status"] == "completed"
    assert result["metric"] == "MAE"
    assert result["score"] == 0.5
    assert result["higher_is_better"] is False
    assert result["evaluation_mode"] == "zero_shot"
    assert result["secondary_metrics"] == {
        "MASE": 0.25,
        "MSE": 0.25,
        "RMSE": 0.5,
        "sMAPE": 10.0,
    }
    assert result["source_versions"] == {"chronos-forecasting": "x.y.z"}


@pytest.mark.parametrize(
    "reason",
    [
        "missing_dependency",
        "unsupported_model_frequency_window",
        "curation_required",
        "data_unavailable",
    ],
)
def test_skipped_result_represents_expected_skip_reasons(reason):
    result = build_skipped_result(sample_task(), reason=reason, message="not runnable")

    assert result["status"] == "skipped"
    assert result["score"] is None
    assert result["error"] == {"reason": reason, "message": "not runnable"}
    assert result["evaluation_mode"] == "zero_shot"


def test_failed_result_captures_runtime_errors():
    result = build_failed_result(sample_task(), reason="runtime_error", message="boom")

    assert result["status"] == "failed"
    assert result["error"] == {"reason": "runtime_error", "message": "boom"}


def test_result_writer_uses_default_suite_run_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = build_completed_result(sample_task(), {"MAE": 0.5}, model_runtime={})

    output_path = write_result(result)

    expected = tmp_path / "data/benchmark/runs/forecasting-v0" / f"{sample_task().run_id}.json"
    assert output_path == expected
    assert json.loads(output_path.read_text())["run_id"] == sample_task().run_id


def test_result_writer_accepts_configurable_output_dir(tmp_path):
    result = build_skipped_result(
        sample_task(),
        reason="data_unavailable",
        message="missing local csv",
    )

    output_path = write_result(result, output_dir=tmp_path / "custom-runs")

    expected = tmp_path / "custom-runs/forecasting-v0" / f"{sample_task().run_id}.json"
    assert output_path == expected
    assert json.loads(output_path.read_text())["status"] == "skipped"
