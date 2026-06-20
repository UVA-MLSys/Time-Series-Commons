from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pandas as pd
import pytest

from tools.benchmark_runner.model_adapters import (
    MissingDependencyError,
    UnsupportedTaskError,
    get_adapter,
)


def make_task(**overrides):
    values = {
        "model_id": "Chronos-2",
        "io_mode": "UV-UV",
        "lookback_window": 4,
        "forecast_horizon": 2,
        "frequency": "hourly",
        "target_variables": ["load"],
        "input_variables": ["load"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_context():
    return pd.DataFrame(
        {
            "item_id": ["series-1"] * 4,
            "timestamp": pd.date_range("2024-01-01", periods=4, freq="h"),
            "variable": ["load"] * 4,
            "value": [1.0, 2.0, 3.0, 4.0],
        }
    )


def make_multivariate_context():
    timestamps = pd.date_range("2024-01-01", periods=4, freq="h")
    return pd.DataFrame(
        {
            "item_id": ["series-1"] * 8,
            "timestamp": list(timestamps) * 2,
            "variable": ["load"] * 4 + ["temp"] * 4,
            "value": [1.0, 2.0, 3.0, 4.0, 10.0, 11.0, 12.0, 13.0],
        }
    )


def test_get_adapter_returns_documented_adapter_contracts():
    expected = {
        "Chronos-2": (
            ("chronos-forecasting",),
            "https://github.com/amazon-science/chronos-forecasting",
        ),
        "TTM-R3-FT": (
            ("granite-tsfm", "tsfm_public"),
            "https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
        ),
        "Moirai2": (
            ("uni2ts", "gluonts"),
            "https://github.com/SalesforceAIResearch/uni2ts",
        ),
    }

    for model_id, (packages, source_url) in expected.items():
        adapter = get_adapter(model_id)
        assert adapter.model_id == model_id
        assert adapter.required_packages == packages
        assert adapter.source_url == source_url
        assert callable(adapter.predict)


def test_unknown_model_raises_unsupported_task_error():
    with pytest.raises(UnsupportedTaskError) as exc:
        get_adapter("Not-A-Model")

    assert exc.value.model_id == "Not-A-Model"
    assert exc.value.reason == "unknown_model"


def test_missing_dependency_error_is_structured_and_does_not_fabricate_predictions(monkeypatch):
    real_import = __import__

    def block_chronos(name, *args, **kwargs):
        if name == "chronos":
            raise ImportError("No module named chronos")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", block_chronos)

    adapter = get_adapter("Chronos-2")
    with pytest.raises(MissingDependencyError) as exc:
        adapter.predict(make_context(), None, make_task())

    assert exc.value.model_id == "Chronos-2"
    assert exc.value.packages == ("chronos-forecasting",)
    assert exc.value.source_url == adapter.source_url
    assert exc.value.reason == "missing_dependency"


def test_ttm_rejects_unsupported_frequency_before_runtime_inference():
    adapter = get_adapter("TTM-R3-FT")
    task = make_task(model_id="TTM-R3-FT", frequency="monthly")

    with pytest.raises(UnsupportedTaskError) as exc:
        adapter.predict(make_context(), None, task)

    assert exc.value.model_id == "TTM-R3-FT"
    assert exc.value.reason == "unsupported_frequency"


def test_ttm_adapter_uses_get_model_and_forecasting_pipeline(monkeypatch):
    calls = {}

    class FakeTorchCuda:
        @staticmethod
        def is_available():
            return False

    fake_torch = types.SimpleNamespace(cuda=FakeTorchCuda())
    fake_model = types.SimpleNamespace(config=types.SimpleNamespace(context_length=4, prediction_length=2))

    def fake_get_model(**kwargs):
        calls["get_model"] = kwargs
        return fake_model

    class FakePipeline:
        def __init__(self, model, **kwargs):
            calls["pipeline_init"] = {"model": model, **kwargs}

        def __call__(self, input_df, **kwargs):
            calls["pipeline_call"] = {"input_df": input_df.copy(), **kwargs}
            return pd.DataFrame(
                {
                    "timestamp": pd.date_range("2024-01-01 04:00", periods=2, freq="h"),
                    "item_id": ["series-1", "series-1"],
                    "load": [0.0, 1.0],
                }
            )

    tsfm_public = types.ModuleType("tsfm_public")
    tsfm_public.TimeSeriesForecastingPipeline = FakePipeline
    toolkit = types.ModuleType("tsfm_public.toolkit")
    get_model_module = types.ModuleType("tsfm_public.toolkit.get_model")
    get_model_module.get_model = fake_get_model

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "tsfm_public", tsfm_public)
    monkeypatch.setitem(sys.modules, "tsfm_public.toolkit", toolkit)
    monkeypatch.setitem(sys.modules, "tsfm_public.toolkit.get_model", get_model_module)

    adapter = get_adapter("TTM-R3-FT")
    result = adapter.predict(make_context(), None, make_task(model_id="TTM-R3-FT"))

    assert calls["get_model"] == {
        "model_path": "ibm-granite/granite-timeseries-ttm-r2",
        "context_length": 4,
        "prediction_length": 2,
        "freq": "h",
        "return_model_key": False,
        "force_return": None,
    }
    assert calls["pipeline_init"]["model"] is fake_model
    assert calls["pipeline_init"]["timestamp_column"] == "timestamp"
    assert calls["pipeline_init"]["id_columns"] == ["item_id"]
    assert calls["pipeline_init"]["target_columns"] == ["load"]
    assert calls["pipeline_init"]["explode_forecasts"] is True
    assert calls["pipeline_init"]["freq"] == "h"
    assert calls["pipeline_init"]["device"] == "cpu"
    assert calls["pipeline_call"]["prediction_length"] == 2
    assert calls["pipeline_call"]["context_length"] == 4
    assert calls["pipeline_call"]["input_df"]["load"].round(6).tolist() == [
        -1.341641,
        -0.447214,
        0.447214,
        1.341641,
    ]
    assert result["prediction"].round(6).tolist() == [2.5, 3.618034]


def test_ttm_rejects_selected_checkpoint_with_mismatched_context_length(monkeypatch):
    fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
    fake_model = types.SimpleNamespace(config=types.SimpleNamespace(context_length=512, prediction_length=720))

    def fake_get_model(**kwargs):
        return fake_model

    tsfm_public = types.ModuleType("tsfm_public")
    tsfm_public.TimeSeriesForecastingPipeline = object
    toolkit = types.ModuleType("tsfm_public.toolkit")
    get_model_module = types.ModuleType("tsfm_public.toolkit.get_model")
    get_model_module.get_model = fake_get_model

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "tsfm_public", tsfm_public)
    monkeypatch.setitem(sys.modules, "tsfm_public.toolkit", toolkit)
    monkeypatch.setitem(sys.modules, "tsfm_public.toolkit.get_model", get_model_module)

    adapter = get_adapter("TTM-R3-FT")

    with pytest.raises(UnsupportedTaskError) as exc:
        adapter.predict(
            make_context(),
            None,
            make_task(
                model_id="TTM-R3-FT",
                lookback_window=720,
                forecast_horizon=720,
                frequency="hourly",
            ),
        )

    assert exc.value.reason == "unsupported_window"


def test_chronos_adapter_uses_documented_predict_df_contract(monkeypatch):
    calls = {}

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, model_name, device_map="auto"):
            calls["from_pretrained"] = {
                "model_name": model_name,
                "device_map": device_map,
            }
            return cls()

        def predict_df(self, context_df, **kwargs):
            calls["context_columns"] = list(context_df.columns)
            calls["context_df"] = context_df.copy()
            calls["kwargs"] = kwargs
            return pd.DataFrame(
                {
                    "id": ["series-1", "series-1"],
                    "timestamp": pd.date_range("2024-01-01 04:00", periods=2, freq="h"),
                    "predictions": [10.0, 11.0],
                    "0.5": [10.0, 11.0],
                }
            )

    monkeypatch.setitem(
        sys.modules,
        "chronos",
        types.SimpleNamespace(Chronos2Pipeline=FakePipeline),
    )

    adapter = get_adapter("Chronos-2", device_map="cpu")
    result = adapter.predict(make_context(), None, make_task())

    assert calls["from_pretrained"] == {
        "model_name": "amazon/chronos-2",
        "device_map": "cpu",
    }
    assert calls["context_columns"] == ["id", "timestamp", "target"]
    assert calls["kwargs"]["future_df"] is None
    assert calls["kwargs"]["prediction_length"] == 2
    assert calls["kwargs"]["quantile_levels"] == [0.5]
    assert calls["kwargs"]["id_column"] == "id"
    assert calls["kwargs"]["timestamp_column"] == "timestamp"
    assert calls["kwargs"]["target"] == "target"
    assert result.to_dict("records") == [
        {
            "item_id": "series-1",
            "timestamp": pd.Timestamp("2024-01-01 04:00"),
            "variable": "load",
            "prediction": 10.0,
        },
        {
            "item_id": "series-1",
            "timestamp": pd.Timestamp("2024-01-01 05:00"),
            "variable": "load",
            "prediction": 11.0,
        },
    ]


def test_chronos_mv_mv_normalizes_wide_predictions_for_each_target_variable(monkeypatch):
    calls = {}

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, model_name, device_map="auto"):
            return cls()

        def predict_df(self, context_df, **kwargs):
            calls["target"] = kwargs["target"]
            return pd.DataFrame(
                {
                    "id": ["series-1", "series-1"],
                    "timestamp": pd.date_range("2024-01-01 04:00", periods=2, freq="h"),
                    "load": [5.0, 6.0],
                    "temp": [14.0, 15.0],
                }
            )

    monkeypatch.setitem(
        sys.modules,
        "chronos",
        types.SimpleNamespace(Chronos2Pipeline=FakePipeline),
    )

    adapter = get_adapter("Chronos-2", device_map="cpu")
    result = adapter.predict(
        make_multivariate_context(),
        None,
        make_task(
            io_mode="MV-MV",
            target_variables=["load", "temp"],
            input_variables=["load", "temp"],
        ),
    )

    assert calls["target"] == ["load", "temp"]
    assert result[["timestamp", "variable", "prediction"]].to_dict("records") == [
        {"timestamp": pd.Timestamp("2024-01-01 04:00"), "variable": "load", "prediction": 5.0},
        {"timestamp": pd.Timestamp("2024-01-01 05:00"), "variable": "load", "prediction": 6.0},
        {"timestamp": pd.Timestamp("2024-01-01 04:00"), "variable": "temp", "prediction": 14.0},
        {"timestamp": pd.Timestamp("2024-01-01 05:00"), "variable": "temp", "prediction": 15.0},
    ]


def test_chronos_mv_mv_rejects_incomplete_generic_prediction_output(monkeypatch):
    class FakePipeline:
        @classmethod
        def from_pretrained(cls, model_name, device_map="auto"):
            return cls()

        def predict_df(self, context_df, **kwargs):
            return pd.DataFrame(
                {
                    "id": ["series-1", "series-1"],
                    "timestamp": pd.date_range("2024-01-01 04:00", periods=2, freq="h"),
                    "prediction": [5.0, 6.0],
                }
            )

    monkeypatch.setitem(
        sys.modules,
        "chronos",
        types.SimpleNamespace(Chronos2Pipeline=FakePipeline),
    )

    adapter = get_adapter("Chronos-2", device_map="cpu")

    with pytest.raises(UnsupportedTaskError) as exc:
        adapter.predict(
            make_multivariate_context(),
            None,
            make_task(
                io_mode="MV-MV",
                target_variables=["load", "temp"],
                input_variables=["load", "temp"],
            ),
        )

    assert exc.value.reason == "unsupported_multitarget"
    assert exc.value.details["missing_variables"] == ["load", "temp"]


def test_moirai2_rejects_mv_mv_until_multitarget_forecasts_are_implemented():
    adapter = get_adapter("Moirai2")

    with pytest.raises(UnsupportedTaskError) as exc:
        adapter.predict(
            make_multivariate_context(),
            None,
            make_task(
                model_id="Moirai2",
                io_mode="MV-MV",
                target_variables=["load", "temp"],
                input_variables=["load", "temp"],
            ),
        )

    assert exc.value.model_id == "Moirai2"
    assert exc.value.reason == "unsupported_multitarget"


def test_moirai2_rejects_large_multivariate_panels_on_colab_t4_budget():
    timestamps = pd.date_range("2024-01-01", periods=336, freq="h")
    variables = [f"sensor_{index}" for index in range(900)]
    frame = pd.DataFrame(
        {
            "item_id": "traffic",
            "timestamp": timestamps.repeat(len(variables)),
            "variable": variables * len(timestamps),
            "value": 1.0,
        }
    )
    adapter = get_adapter("Moirai2")

    with pytest.raises(UnsupportedTaskError) as exc:
        adapter.predict(
            frame,
            None,
            make_task(
                model_id="Moirai2",
                io_mode="MV-UV",
                lookback_window=336,
                forecast_horizon=168,
                target_variables=["sensor_0"],
                input_variables=variables,
            ),
        )

    assert exc.value.reason == "resource_budget_exceeded"


def test_moirai2_rejects_ecl_sized_medium_panels_on_colab_t4_budget():
    timestamps = pd.date_range("2024-01-01", periods=336, freq="h")
    variables = [f"meter_{index}" for index in range(321)]
    frame = pd.DataFrame(
        {
            "item_id": "ecl",
            "timestamp": timestamps.repeat(len(variables)),
            "variable": variables * len(timestamps),
            "value": 1.0,
        }
    )
    adapter = get_adapter("Moirai2")

    with pytest.raises(UnsupportedTaskError) as exc:
        adapter.predict(
            frame,
            None,
            make_task(
                model_id="Moirai2",
                io_mode="MV-UV",
                lookback_window=336,
                forecast_horizon=168,
                target_variables=["meter_0"],
                input_variables=variables,
            ),
        )

    assert exc.value.reason == "resource_budget_exceeded"
    assert exc.value.details["panel_width"] == 321
