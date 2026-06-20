import json
from pathlib import Path


EXAMPLE_PATH = Path("data/benchmark/runs/examples/example-run-result.json")


def test_example_benchmark_is_an_executable_specification_and_result_ledger():
    benchmark = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    assert benchmark["schema_version"] == "0.2.0"
    assert benchmark["evaluation_mode"] == "zero_shot"
    assert set(benchmark["model_profiles"]) == {
        "Chronos-2",
        "TTM-R3-FT",
        "Moirai2",
    }
    assert set(benchmark["window_profiles"]["hourly"]) == {
        "short",
        "medium",
        "long",
    }

    run = benchmark["runs"][0]
    assert run["models"] == ["Chronos-2", "TTM-R3-FT", "Moirai2"]
    assert run["io_mode"] == "MV-UV"
    assert run["variables"]["targets"] == ["OT"]
    assert "HUFL" in run["variables"]["observed"]
    assert run["variables"]["known_future"] == []

    result = benchmark["results"]["etth1-mv-uv__Chronos-2__short"]
    assert result["status"] == "completed"
    assert set(result["metrics"]) == {"MAE", "MSE", "RMSE"}
    assert result["resolved_config"]["targets"] == run["variables"]["targets"]
    assert result["attempts"][-1]["metrics"] == result["metrics"]
