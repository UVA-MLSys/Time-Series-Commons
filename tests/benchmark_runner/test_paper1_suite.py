import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_paper1_suite_uses_doc_window_rules():
    suite = json.loads((ROOT / "data/benchmark/paper1-suite.json").read_text())
    rules = suite["window_rules"]

    assert rules["hourly"]["short"] == {"lookback_window": 72, "forecast_horizon": 24}
    assert rules["hourly"]["medium"] == {"lookback_window": 336, "forecast_horizon": 168}
    assert rules["hourly"]["long"] == {"lookback_window": 720, "forecast_horizon": 720}
    assert rules["daily"]["short"] == {"lookback_window": 30, "forecast_horizon": 7}
    assert rules["daily"]["medium"] == {"lookback_window": 90, "forecast_horizon": 30}
    assert rules["daily"]["long"] == {"lookback_window": 365, "forecast_horizon": 90}
    assert rules["weekly"]["short"] == {"lookback_window": 13, "forecast_horizon": 4}
    assert rules["monthly"]["short"] == {"lookback_window": 24, "forecast_horizon": 6}
    assert rules["ten_minute"]["short"] == {"lookback_window": 432, "forecast_horizon": 144}
    assert rules["ten_minute"]["medium"] == {"lookback_window": 2016, "forecast_horizon": 1008}
    assert rules["ten_minute"]["long"] == {"lookback_window": 4320, "forecast_horizon": 4320}
    assert rules["m4_hourly"]["medium"] == {"lookback_window": 336, "forecast_horizon": 48}
    assert rules["m4_hourly"]["long"] == {"lookback_window": 720, "forecast_horizon": 168}
    assert rules["m4_daily"]["medium"] == {"lookback_window": 90, "forecast_horizon": 14}
    assert rules["m4_daily"]["long"] == {"lookback_window": 365, "forecast_horizon": 30}


def test_paper1_suite_is_zero_shot_only_with_three_common_models():
    suite = json.loads((ROOT / "data/benchmark/paper1-suite.json").read_text())
    assert suite["models"] == ["Chronos-2", "TTM-R3-FT", "Moirai2"]
    assert suite["evaluation_modes"] == ["zero_shot"]


def test_paper1_suite_includes_required_datasets():
    suite = json.loads((ROOT / "data/benchmark/paper1-suite.json").read_text())
    ids = {d["suite_dataset_id"] for d in suite["datasets"]}
    assert ids == {
        "paper1_etth1",
        "paper1_ecl",
        "paper1_traffic",
        "paper1_weather_jena",
        "paper1_exchange",
        "paper1_m4_hourly",
        "paper1_m4_daily",
        "paper1_m4_monthly",
        "paper1_ili",
        "paper1_camels_us",
    }


def test_paper1_huggingface_suite_entries_reference_unique_registry_keys():
    suite = json.loads((ROOT / "data/benchmark/paper1-suite.json").read_text())
    datasets = {
        dataset["suite_dataset_id"]: dataset
        for dataset in suite["datasets"]
        if dataset["suite_dataset_id"] != "paper1_camels_us"
    }

    assert {dataset["benchmark_id"] for dataset in datasets.values()} == {
        "etth1_thuml",
        "electricity_ecl_thuml",
        "traffic_thuml",
        "weather_jena_thuml",
        "exchange_rate_thuml",
        "m4_hourly_thuml",
        "m4_daily_thuml",
        "m4_monthly_thuml",
        "ili_thuml",
    }
    assert datasets["paper1_traffic"].get("curation_required") is not True
    assert datasets["paper1_weather_jena"]["frequency_rule"] == "ten_minute"
    assert datasets["paper1_m4_hourly"]["frequency_rule"] == "m4_hourly"
    assert datasets["paper1_m4_daily"]["frequency_rule"] == "m4_daily"
    assert datasets["paper1_m4_monthly"]["frequency_rule"] == "m4_monthly"


def test_camels_us_remains_deferred_for_manual_implementation():
    suite = json.loads((ROOT / "data/benchmark/paper1-suite.json").read_text())
    camels = next(dataset for dataset in suite["datasets"] if dataset["suite_dataset_id"] == "paper1_camels_us")

    assert camels["curation_required"] is True
    assert "benchmark_id" not in camels
