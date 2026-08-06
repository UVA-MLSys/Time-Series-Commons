from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Iterable

import numpy as np
import pandas as pd


class MissingDependencyError(RuntimeError):
    """Raised when an optional runtime package for a model adapter is absent."""

    reason = "missing_dependency"

    def __init__(
        self,
        model_id: str,
        packages: tuple[str, ...],
        source_url: str,
        original_error: BaseException | None = None,
    ):
        self.model_id = model_id
        self.packages = packages
        self.source_url = source_url
        self.original_error = original_error
        package_text = ", ".join(packages)
        super().__init__(
            f"{model_id} requires optional package(s): {package_text}. "
            f"Install them using the official adapter source: {source_url}"
        )


class UnsupportedTaskError(RuntimeError):
    """Raised when a model adapter cannot support a requested task."""

    def __init__(
        self,
        model_id: str,
        reason: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.model_id = model_id
        self.reason = reason
        self.details = details or {}
        super().__init__(message or f"{model_id} does not support this task: {reason}")


@dataclass
class BaseAdapter:
    model_id: str
    required_packages: tuple[str, ...]
    source_url: str
    device_map: str = "auto"

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        raise NotImplementedError


def get_adapter(model_id: str, **kwargs: Any) -> BaseAdapter:
    adapters = {
        Chronos2Adapter.model_id: Chronos2Adapter,
        StrideChronos2Adapter.model_id: StrideChronos2Adapter,
        TTMAdapter.model_id: TTMAdapter,
        Moirai2Adapter.model_id: Moirai2Adapter,
        TimesFM25Adapter.model_id: TimesFM25Adapter,
        Toto2Adapter.model_id: Toto2Adapter,
        Tirex2PretrainedAdapter.model_id: Tirex2PretrainedAdapter,
        GraniteFlowStateAdapter.model_id: GraniteFlowStateAdapter,
        PatchTSTFMAdapter.model_id: PatchTSTFMAdapter,
    }
    try:
        return adapters[model_id](**kwargs)
    except KeyError as exc:
        raise UnsupportedTaskError(model_id, "unknown_model") from exc


def _task_value(task: Any, name: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(name, default)
    return getattr(task, name, default)


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"forecast adapter input is missing required columns: {missing}")


def _target_variables(context_df: pd.DataFrame, task: Any) -> tuple[str, ...]:
    requested = (
        _task_value(task, "target_variables")
        or _task_value(task, "output_variables")
        or _task_value(task, "target_variable")
        or _task_value(task, "target_streams")
    )
    if requested:
        return _as_tuple(requested)
    _require_columns(context_df, ("variable",))
    return tuple(dict.fromkeys(context_df["variable"].astype(str)))


def _input_variables(context_df: pd.DataFrame, task: Any) -> tuple[str, ...]:
    requested = (
        _task_value(task, "input_variables")
        or _task_value(task, "variables")
        or _task_value(task, "observed_streams")
    )
    if requested:
        return _as_tuple(requested)
    _require_columns(context_df, ("variable",))
    return tuple(dict.fromkeys(context_df["variable"].astype(str)))


def _prediction_length(task: Any) -> int:
    value = _task_value(task, "forecast_horizon")
    if value is None:
        value = _task_value(task, "prediction_length")
    if value is None:
        raise ValueError("task must define forecast_horizon or prediction_length")
    return int(value)


def _context_length(task: Any) -> int:
    value = _task_value(task, "lookback_window")
    if value is None:
        value = _task_value(task, "context_length")
    if value is None:
        raise ValueError("task must define lookback_window or context_length")
    return int(value)


def _frequency(task: Any) -> str | None:
    value = _task_value(task, "frequency_rule_or_mapped_freq")
    if value is None:
        value = _task_value(task, "mapped_frequency")
    if value is None:
        value = _task_value(task, "frequency")
    if value is None:
        return None
    return str(value).lower()


def _freq_alias(task: Any) -> str | None:
    mapping = {
        "5t": "5min",
        "5min": "5min",
        "5 min": "5min",
        "10t": "10min",
        "10min": "10min",
        "10 min": "10min",
        "15t": "15min",
        "15min": "15min",
        "15 min": "15min",
        "30t": "30min",
        "30min": "30min",
        "30 min": "30min",
        "s": "s",
        "second": "s",
        "seconds": "s",
        "10s": "10s",
        "10 sec": "10s",
        "10 seconds": "10s",
        "m": "m",
        "monthly": "m",
        "month": "m",
        "minutely": "min",
        "minute": "min",
        "t": "min",
        "h": "h",
        "hourly": "h",
        "hour": "h",
        "d": "d",
        "daily": "d",
        "day": "d",
        "w": "w",
        "weekly": "w",
        "week": "w",
    }
    value = _frequency(task)
    if value is None:
        return None
    return mapping.get(value, value)


def _long_to_wide(frame: pd.DataFrame, variables: tuple[str, ...]) -> pd.DataFrame:
    _require_columns(frame, ("item_id", "timestamp", "variable", "value"))
    selected = frame[frame["variable"].astype(str).isin(variables)].copy()
    wide = selected.pivot(
        index=["item_id", "timestamp"],
        columns="variable",
        values="value",
    ).reset_index()
    wide.columns.name = None
    return wide.sort_values(["item_id", "timestamp"]).reset_index(drop=True)


def _panel_width(frame: pd.DataFrame) -> int:
    return int(frame["variable"].nunique()) if "variable" in frame.columns else 1


def _torch_device(torch_module: Any, device_map: str = "auto") -> Any:
    if device_map and device_map != "auto":
        return torch_module.device(str(device_map))
    if torch_module.cuda.is_available():
        return torch_module.device("cuda")
    mps = getattr(torch_module, "mps", None)
    if mps is not None and callable(getattr(mps, "is_available", None)) and mps.is_available():
        return torch_module.device("mps")
    return torch_module.device("cpu")


def _single_series_entries(context_df: pd.DataFrame, target_variables: tuple[str, ...]) -> list[dict[str, Any]]:
    _require_columns(context_df, ("item_id", "timestamp", "variable", "value"))
    selected = context_df[context_df["variable"].astype(str).isin(target_variables)].copy()
    selected["timestamp"] = pd.to_datetime(selected["timestamp"])
    selected["value"] = pd.to_numeric(selected["value"], errors="coerce")

    entries: list[dict[str, Any]] = []
    for (item_id, variable), group in selected.groupby(["item_id", "variable"], sort=False):
        ordered = group.sort_values("timestamp")
        entries.append(
            {
                "item_id": str(item_id),
                "variable": str(variable),
                "last_timestamp": pd.Timestamp(ordered["timestamp"].iloc[-1]),
                "freq": _infer_group_frequency(ordered),
                "target": ordered["value"].astype(float).to_numpy(),
            }
        )
    return entries


def _infer_group_frequency(frame: pd.DataFrame) -> str:
    timestamps = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"]).drop_duplicates().sort_values())
    if len(timestamps) >= 3:
        inferred = pd.infer_freq(timestamps)
        if inferred:
            return inferred
    if len(timestamps) >= 2:
        delta = timestamps[-1] - timestamps[-2]
        offset = pd.tseries.frequencies.to_offset(delta)
        return offset.freqstr
    return "D"


def _single_series_forecasts_to_frame(
    forecasts: list[np.ndarray],
    entries: list[dict[str, Any]],
    task: Any,
) -> pd.DataFrame:
    if len(forecasts) != len(entries):
        raise ValueError(f"model produced {len(forecasts)} forecasts for {len(entries)} target series")

    rows: list[pd.DataFrame] = []
    horizon = _prediction_length(task)
    for entry, values in zip(entries, forecasts, strict=True):
        series = pd.Series(np.asarray(values, dtype=float).reshape(-1)).head(horizon)
        timestamps = pd.date_range(
            entry["last_timestamp"],
            periods=horizon + 1,
            freq=entry["freq"],
        )[1 : len(series) + 1]
        rows.append(
            pd.DataFrame(
                {
                    "item_id": entry["item_id"],
                    "timestamp": timestamps,
                    "variable": entry["variable"],
                    "prediction": series.astype(float).to_numpy(),
                }
            )
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["item_id", "timestamp", "variable", "prediction"]
    )


def _extract_1d_forecast(values: Any, horizon: int) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        raise ValueError("model returned a scalar forecast")
    if array.ndim == 1:
        return array[:horizon]
    if array.ndim == 2:
        if 1 in array.shape:
            return array.reshape(-1)[:horizon]
        if array.shape[0] >= horizon:
            return array[:horizon, 0]
        return array[0, :horizon]
    if array.ndim == 3:
        if array.shape[0] == 1:
            return _extract_1d_forecast(array[0], horizon)
        if array.shape[-1] == 1:
            return _extract_1d_forecast(array[..., 0], horizon)
    if array.ndim == 4:
        if array.shape[0] == 1:
            return _extract_1d_forecast(array[0], horizon)
        if array.shape[-1] == 1:
            return _extract_1d_forecast(array[..., 0], horizon)
    raise ValueError(f"model returned an unsupported forecast shape: {array.shape}")


def _normalize_point_forecast(
    pred_df: pd.DataFrame,
    target_variables: tuple[str, ...],
    default_item_id: Any | None = None,
) -> pd.DataFrame:
    if pred_df.empty:
        return pd.DataFrame(columns=["item_id", "timestamp", "variable", "prediction"])

    frame = pred_df.copy()
    if "item_id" not in frame.columns:
        if "id" in frame.columns:
            frame = frame.rename(columns={"id": "item_id"})
        elif default_item_id is not None:
            frame["item_id"] = default_item_id
    if "timestamp" not in frame.columns:
        raise ValueError("model forecast output must include a timestamp column")

    value_columns = [column for column in target_variables if column in frame.columns]
    if value_columns:
        result = frame.melt(
            id_vars=["item_id", "timestamp"],
            value_vars=value_columns,
            var_name="variable",
            value_name="prediction",
        )
        return result.sort_values(["item_id", "variable", "timestamp"]).reset_index(drop=True)

    point_column = None
    for candidate in ("prediction", "predictions", "mean", "0.5", 0.5):
        if candidate in frame.columns:
            point_column = candidate
            break

    if point_column is not None:
        variable = target_variables[0] if len(target_variables) == 1 else "target"
        if "variable" not in frame.columns:
            frame["variable"] = variable
        result = frame[["item_id", "timestamp", "variable", point_column]].rename(
            columns={point_column: "prediction"}
        )
        return result.reset_index(drop=True)

    raise ValueError("model forecast output does not contain a point forecast column")


def _ensure_target_variables(
    forecast: pd.DataFrame,
    target_variables: tuple[str, ...],
    model_id: str,
) -> None:
    if len(target_variables) <= 1 or "variable" not in forecast.columns:
        return
    observed = set(forecast["variable"].astype(str))
    missing = sorted(str(variable) for variable in target_variables if str(variable) not in observed)
    if missing:
        raise UnsupportedTaskError(
            model_id,
            "unsupported_multitarget",
            "Model output did not include forecasts for every requested target variable.",
            {
                "target_variables": list(target_variables),
                "missing_variables": missing,
                "observed_variables": sorted(observed),
            },
        )


@dataclass
class Chronos2Adapter(BaseAdapter):
    model_id: str = "Chronos-2"
    required_packages: tuple[str, ...] = ("chronos-forecasting",)
    source_url: str = "https://github.com/amazon-science/chronos-forecasting"
    device_map: str = "auto"
    _pipeline: Any | None = field(default=None, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        pipeline = self._get_pipeline()
        target_variables = _target_variables(context_df, task)
        io_mode = _task_value(task, "io_mode", "UV-UV")
        if io_mode in {"UV-UV", "MV-MV"} and len(target_variables) > 1:
            forecasts = [
                self._predict_single_target(pipeline, context_df, future_df, task, target_variable)
                for target_variable in target_variables
            ]
            return pd.concat(forecasts, ignore_index=True)

        return self._predict_single_target(pipeline, context_df, future_df, task, target_variables[0])

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        try:
            from chronos import Chronos2Pipeline
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        self._pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=self.device_map)
        return self._pipeline

    def _predict_single_target(
        self,
        pipeline: Any,
        context_df: pd.DataFrame,
        future_df: pd.DataFrame | None,
        task: Any,
        target_variable: str,
    ) -> pd.DataFrame:
        context, future = self._prepare_predict_df_inputs(
            context_df,
            future_df,
            task,
            target_variable,
        )
        pred_df = self._predict_df_by_context_length(
            pipeline,
            context,
            future,
            prediction_length=_prediction_length(task),
        )
        return _normalize_point_forecast(pred_df, (target_variable,))

    def _predict_df_by_context_length(
        self,
        pipeline: Any,
        context: pd.DataFrame,
        future: pd.DataFrame | None,
        *,
        prediction_length: int,
    ) -> pd.DataFrame:
        if "id" not in context.columns:
            return self._call_predict_df(pipeline, context, future, prediction_length)

        lengths = context.groupby("id", sort=False)["timestamp"].nunique()
        if lengths.nunique() <= 1:
            return self._call_predict_df(pipeline, context, future, prediction_length)

        predictions = []
        seen_lengths: list[int] = []
        for length in lengths.tolist():
            if int(length) not in seen_lengths:
                seen_lengths.append(int(length))

        for length in seen_lengths:
            ids = lengths[lengths == length].index
            context_part = context[context["id"].isin(ids)]
            future_part = future[future["id"].isin(ids)] if future is not None and "id" in future.columns else future
            predictions.append(self._call_predict_df(pipeline, context_part, future_part, prediction_length))
        return pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()

    def _call_predict_df(
        self,
        pipeline: Any,
        context: pd.DataFrame,
        future: pd.DataFrame | None,
        prediction_length: int,
    ) -> pd.DataFrame:
        return pipeline.predict_df(
            context,
            future_df=future,
            prediction_length=prediction_length,
            quantile_levels=[0.5],
            id_column="id",
            timestamp_column="timestamp",
            target="target",
        )

    def _prepare_predict_df_inputs(
        self,
        context_df: pd.DataFrame,
        future_df: pd.DataFrame | None,
        task: Any,
        target_variable: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        if _task_value(task, "io_mode", "UV-UV") == "UV-UV":
            input_variables = (target_variable,)
        else:
            input_variables = _input_variables(context_df, task)
        variables = tuple(dict.fromkeys((target_variable, *input_variables)))
        context = _long_to_wide(context_df, variables).rename(columns={"item_id": "id"})
        context = context.rename(columns={target_variable: "target"})

        future = None
        if future_df is not None and not future_df.empty:
            covariates = tuple(variable for variable in input_variables if variable != target_variable)
            if covariates and "value" in future_df.columns:
                future = _long_to_wide(future_df, covariates).rename(columns={"item_id": "id"})
        return context, future


@dataclass
class StrideChronos2Adapter(Chronos2Adapter):
    model_id: str = "STRIDE-Chronos2"
    source_url: str = "https://github.com/amazon-science/chronos-forecasting"


@dataclass
class TTMAdapter(BaseAdapter):
    model_id: str = "TTM-R3-FT"
    required_packages: tuple[str, ...] = ("granite-tsfm", "tsfm_public")
    source_url: str = "https://huggingface.co/ibm-research/ttm-r3"
    model_path: str = "ibm-research/ttm-r3"
    use_lite: bool = False
    _models: dict[tuple[int, int, str | None], Any] = field(default_factory=dict, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        self._validate_task(task)
        try:
            import torch
            from tsfm_public import TimeSeriesForecastingPipeline
            from tsfm_public.toolkit.get_model import get_model
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        model = self._select_model(get_model, task)
        target_variables = _target_variables(context_df, task)
        selected_context = self._selected_context_length(model, task)
        model_context_df = self._tail_context(context_df, target_variables, selected_context)
        scaled, stats = self._standard_scale(model_context_df, target_variables)

        try:
            predictions = self._predict_with_model(
                model,
                TimeSeriesForecastingPipeline,
                torch,
                scaled,
                future_df,
                task,
                target_variables,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_runtime_api",
                "Installed Granite TSFM model does not expose a supported zero-shot inference API.",
            ) from exc

        return self._invert_scale(predictions, stats)

    def _validate_task(self, task: Any) -> None:
        freq = _freq_alias(task)
        if freq not in {"10min", "15min", "min", "h", "d", "w"}:
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_frequency",
                "TTM R2 supports minutely/hourly and R2.1 adds daily/weekly; this task frequency is unsupported.",
                {"frequency": _frequency(task)},
            )

    def _select_model(self, get_model: Any, task: Any) -> Any:
        cache_key = (_context_length(task), _prediction_length(task), _freq_alias(task))
        if cache_key in self._models:
            return self._models[cache_key]
        try:
            model = get_model(
                model_path=self.model_path,
                context_length=_context_length(task),
                prediction_length=_prediction_length(task),
                freq=_freq_alias(task),
                return_model_key=False,
                force_return=None,
                use_lite=self.use_lite,
            )
        except Exception as exc:
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_window",
                "No documented TTM checkpoint supports the requested context, horizon, and frequency without zero-padding or excessive rolling.",
                {
                    "context_length": _context_length(task),
                    "prediction_length": _prediction_length(task),
                    "frequency": _frequency(task),
                },
            ) from exc
        config = getattr(model, "config", None)
        selected_context = int(getattr(config, "context_length", _context_length(task)))
        selected_prediction = int(getattr(config, "prediction_length", _prediction_length(task)))
        if selected_context > _context_length(task) or selected_prediction < _prediction_length(task):
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_window",
                "Selected TTM checkpoint cannot cover the requested context and horizon.",
                {
                    "requested_context_length": _context_length(task),
                    "requested_prediction_length": _prediction_length(task),
                    "selected_context_length": selected_context,
                    "selected_prediction_length": selected_prediction,
                },
            )
        self._models[cache_key] = model
        return model

    def _selected_context_length(self, model: Any, task: Any) -> int:
        config = getattr(model, "config", None)
        return int(getattr(config, "context_length", _context_length(task)))

    def _tail_context(
        self,
        context_df: pd.DataFrame,
        variables: tuple[str, ...],
        selected_context: int,
    ) -> pd.DataFrame:
        _require_columns(context_df, ("item_id", "timestamp", "variable", "value"))
        selected = context_df[context_df["variable"].astype(str).isin(variables)].copy()
        selected["timestamp"] = pd.to_datetime(selected["timestamp"])
        rows: list[pd.DataFrame] = []
        for (_item_id, _variable), group in selected.groupby(["item_id", "variable"], sort=False):
            rows.append(group.sort_values("timestamp").tail(selected_context))
        return pd.concat(rows, ignore_index=True) if rows else selected.iloc[0:0].copy()

    def _standard_scale(
        self, context_df: pd.DataFrame, variables: tuple[str, ...]
    ) -> tuple[pd.DataFrame, dict[tuple[Any, str], tuple[float, float]]]:
        frame = context_df.copy()
        frame["value"] = pd.to_numeric(frame["value"], errors="raise").astype(float)
        stats: dict[tuple[Any, str], tuple[float, float]] = {}
        for (item_id, variable), group in frame.groupby(["item_id", "variable"], sort=False):
            if variable not in variables:
                continue
            mean = float(group["value"].mean())
            std = float(group["value"].std(ddof=0)) or 1.0
            stats[(item_id, variable)] = (mean, std)
            frame.loc[group.index, "value"] = (group["value"] - mean) / std
        return frame, stats

    def _predict_with_model(
        self,
        model: Any,
        pipeline_cls: Any,
        torch_module: Any,
        scaled_context: pd.DataFrame,
        future_df: pd.DataFrame | None,
        task: Any,
        variables: tuple[str, ...],
    ) -> pd.DataFrame:
        input_df = _long_to_wide(scaled_context, variables)
        id_columns = ["item_id"] if "item_id" in input_df.columns else []
        device = "cuda" if torch_module.cuda.is_available() else "cpu"
        pipeline = pipeline_cls(
            model,
            timestamp_column="timestamp",
            id_columns=id_columns,
            target_columns=list(variables),
            explode_forecasts=True,
            freq=_freq_alias(task),
            device=device,
        )
        kwargs: dict[str, Any] = {
            "prediction_length": _prediction_length(task),
            "context_length": self._selected_context_length(model, task),
        }
        if future_df is not None and not future_df.empty:
            kwargs["future_time_series"] = _long_to_wide(future_df, variables)
        pred = pipeline(input_df, **kwargs)
        if isinstance(pred, pd.DataFrame):
            default_item_id = input_df["item_id"].iloc[0] if "item_id" in input_df.columns else None
            return _normalize_point_forecast(pred, variables, default_item_id=default_item_id)
        raise TypeError("TTM pipeline did not return a pandas DataFrame")

    def _invert_scale(
        self, predictions: pd.DataFrame, stats: dict[tuple[Any, str], tuple[float, float]]
    ) -> pd.DataFrame:
        result = predictions.copy()
        for index, row in result.iterrows():
            mean, std = stats.get((row["item_id"], row["variable"]), (0.0, 1.0))
            result.at[index, "prediction"] = (float(row["prediction"]) * std) + mean
        return result


@dataclass
class Moirai2Adapter(BaseAdapter):
    model_id: str = "Moirai2"
    required_packages: tuple[str, ...] = ("uni2ts", "gluonts")
    source_url: str = "https://github.com/SalesforceAIResearch/uni2ts"
    batch_size: int = 1
    _module: Any | None = field(default=None, init=False, repr=False)
    _predictors: dict[tuple[int, int], Any] = field(default_factory=dict, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        target_variables = _target_variables(context_df, task)
        if _task_value(task, "io_mode", "UV-UV") == "MV-MV" and len(target_variables) > 1:
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_multitarget",
                "Moirai2 adapter currently supports single-target forecasts only; MV-MV requires target_dim per target variable.",
                {"target_variables": list(target_variables)},
            )

        panel_width = _panel_width(context_df)
        if panel_width >= 300 and _context_length(task) >= 336:
            raise UnsupportedTaskError(
                self.model_id,
                "resource_budget_exceeded",
                "Moirai2 high-dimensional panel exceeds the default Colab T4 resource budget.",
                {
                    "panel_width": panel_width,
                    "context_length": _context_length(task),
                    "forecast_horizon": _prediction_length(task),
                },
            )

        try:
            from gluonts.dataset.common import ListDataset
            from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        entries = self._context_entries(context_df, target_variables)
        if not entries:
            raise ValueError("Moirai2 received no target series to forecast")

        dataset = ListDataset(
            [
                {
                    "item_id": entry["encoded_id"],
                    "start": entry["start"],
                    "target": entry["target"],
                }
                for entry in entries
            ],
            freq=self._infer_entry_frequency(context_df),
        )
        predictor = self._get_predictor(Moirai2Forecast, Moirai2Module, task)
        forecasts = predictor.predict(dataset)
        return self._forecasts_to_frame(forecasts, entries, task)

    def _get_predictor(self, forecast_cls: Any, module_cls: Any, task: Any) -> Any:
        key = (_context_length(task), _prediction_length(task))
        if key in self._predictors:
            return self._predictors[key]
        if self._module is None:
            self._module = module_cls.from_pretrained("Salesforce/moirai-2.0-R-small")
        model = forecast_cls(
            module=self._module,
            prediction_length=_prediction_length(task),
            context_length=_context_length(task),
            target_dim=1,
            feat_dynamic_real_dim=0,
            past_feat_dynamic_real_dim=0,
        )
        predictor = model.create_predictor(batch_size=self.batch_size)
        self._predictors[key] = predictor
        return predictor

    def _context_entries(
        self,
        context_df: pd.DataFrame,
        target_variables: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        _require_columns(context_df, ("item_id", "timestamp", "variable", "value"))
        selected = context_df[context_df["variable"].astype(str).isin(target_variables)].copy()
        selected["timestamp"] = pd.to_datetime(selected["timestamp"])
        selected["value"] = pd.to_numeric(selected["value"], errors="raise")
        entries: list[dict[str, Any]] = []
        for (item_id, variable), group in selected.groupby(["item_id", "variable"], sort=False):
            ordered = group.sort_values("timestamp")
            entries.append(
                {
                    "item_id": str(item_id),
                    "variable": str(variable),
                    "encoded_id": f"{item_id}\u001f{variable}",
                    "start": pd.Period(
                        ordered["timestamp"].iloc[0],
                        freq=self._infer_group_frequency(ordered),
                    ),
                    "last_timestamp": pd.Timestamp(ordered["timestamp"].iloc[-1]),
                    "freq": self._infer_group_frequency(ordered),
                    "target": ordered["value"].astype(float).tolist(),
                }
            )
        return entries

    def _infer_entry_frequency(self, context_df: pd.DataFrame) -> str:
        return self._infer_group_frequency(context_df)

    def _infer_group_frequency(self, frame: pd.DataFrame) -> str:
        timestamps = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"]).drop_duplicates().sort_values())
        if len(timestamps) >= 3:
            inferred = pd.infer_freq(timestamps)
            if inferred:
                return inferred
        if len(timestamps) >= 2:
            delta = timestamps[-1] - timestamps[-2]
            offset = pd.tseries.frequencies.to_offset(delta)
            return offset.freqstr
        return "D"

    def _forecasts_to_frame(
        self,
        forecasts: Iterable[Any],
        entries: list[dict[str, Any]],
        task: Any,
    ) -> pd.DataFrame:
        rows: list[pd.DataFrame] = []
        for entry, forecast in zip(entries, forecasts, strict=False):
            values = self._forecast_values(forecast)
            if values is None:
                raise ValueError("Moirai2 forecast does not expose median, mean, or quantile output")

            series = pd.Series(values).head(_prediction_length(task))
            timestamps = pd.date_range(
                entry["last_timestamp"],
                periods=_prediction_length(task) + 1,
                freq=entry["freq"],
            )[1 : len(series) + 1]
            rows.append(
                pd.DataFrame(
                    {
                        "item_id": entry["item_id"],
                        "timestamp": timestamps,
                        "variable": entry["variable"],
                        "prediction": series.astype(float).to_numpy(),
                    }
                )
            )
        if len(rows) != len(entries):
            raise ValueError(
                f"Moirai2 produced {len(rows)} forecasts for {len(entries)} target series"
            )
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
            columns=["item_id", "timestamp", "variable", "prediction"]
        )

    def _forecast_values(self, forecast: Any) -> Any:
        for attr in ("median", "mean"):
            if hasattr(forecast, attr):
                values = getattr(forecast, attr)
                if values is not None:
                    return values
        if hasattr(forecast, "quantile"):
            values = forecast.quantile(0.5)
            if values is not None:
                return values
        return None


@dataclass
class TimesFM25Adapter(BaseAdapter):
    model_id: str = "TimesFM-2.5"
    required_packages: tuple[str, ...] = ("timesfm",)
    source_url: str = "https://github.com/google-research/timesfm"
    batch_size: int = 1024
    _model: Any | None = field(default=None, init=False, repr=False)
    _configs: Any | None = field(default=None, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        if _task_value(task, "io_mode", "UV-UV") != "UV-UV":
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_io_mode",
                "TimesFM-2.5 is wired for the official Gift-Eval univariate evaluation path.",
                {"io_mode": _task_value(task, "io_mode", "UV-UV")},
            )

        target_variables = _target_variables(context_df, task)
        entries = self._context_entries(context_df, target_variables)
        if not entries:
            raise ValueError("TimesFM-2.5 received no target series to forecast")

        model, configs = self._get_model()
        forecast_values: list[np.ndarray] = []
        for start in range(0, len(entries), self.batch_size):
            batch = entries[start : start + self.batch_size]
            forecast_values.extend(self._forecast_batch(model, configs, batch, task))
        return self._forecasts_to_frame(forecast_values, entries, task)

    def _get_model(self) -> tuple[Any, Any]:
        if self._model is not None and self._configs is not None:
            return self._model, self._configs

        try:
            import timesfm
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        if hasattr(timesfm, "ForecastConfig") and hasattr(timesfm, "TimesFM_2p5_200M_torch"):
            self._configs = timesfm
            self._model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                "google/timesfm-2.5-200m-pytorch"
            )
        else:
            try:
                from timesfm import configs
                from timesfm.timesfm_2p5 import timesfm_2p5_torch
            except ImportError as exc:
                raise MissingDependencyError(
                    self.model_id, self.required_packages, self.source_url, exc
                ) from exc

            self._configs = configs
            self._model = timesfm_2p5_torch.TimesFM_2p5_200M_torch()
            self._model.load_checkpoint()
        return self._model, self._configs

    def _context_entries(
        self,
        context_df: pd.DataFrame,
        target_variables: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        _require_columns(context_df, ("item_id", "timestamp", "variable", "value"))
        selected = context_df[context_df["variable"].astype(str).isin(target_variables)].copy()
        selected["timestamp"] = pd.to_datetime(selected["timestamp"])
        selected["value"] = pd.to_numeric(selected["value"], errors="raise")

        entries: list[dict[str, Any]] = []
        for (item_id, variable), group in selected.groupby(["item_id", "variable"], sort=False):
            ordered = group.sort_values("timestamp")
            entries.append(
                {
                    "item_id": str(item_id),
                    "variable": str(variable),
                    "last_timestamp": pd.Timestamp(ordered["timestamp"].iloc[-1]),
                    "freq": self._infer_group_frequency(ordered),
                    "target": ordered["value"].astype(float).to_numpy(),
                }
            )
        return entries

    def _forecast_batch(
        self,
        model: Any,
        configs: Any,
        entries: list[dict[str, Any]],
        task: Any,
    ) -> list[np.ndarray]:
        contexts = [entry["target"] for entry in entries]
        max_context = max(int(context.shape[0]) for context in contexts)
        patch_size = int(getattr(getattr(model, "model", None), "p", 1) or 1)
        rounded_context = ((max_context + patch_size - 1) // patch_size) * patch_size
        model.compile(
            forecast_config=configs.ForecastConfig(
                max_context=min(15360, rounded_context),
                max_horizon=1024,
                infer_is_positive=True,
                use_continuous_quantile_head=True,
                fix_quantile_crossing=True,
                force_flip_invariance=True,
                return_backcast=False,
                normalize_inputs=True,
                per_core_batch_size=128,
            ),
        )
        _, full_preds = model.forecast(
            horizon=_prediction_length(task),
            inputs=contexts,
        )
        return [row for row in self._median_predictions(full_preds, task)]

    def _median_predictions(self, full_preds: Any, task: Any) -> np.ndarray:
        horizon = _prediction_length(task)
        values = np.asarray(full_preds, dtype=float)
        if values.ndim == 2:
            return values[:, :horizon]
        if values.ndim != 3:
            raise ValueError(f"TimesFM-2.5 returned an unsupported forecast shape: {values.shape}")

        quantile_values = values[:, :horizon, 1:] if values.shape[2] > 1 else values[:, :horizon, :]
        if quantile_values.shape[2] == 0:
            raise ValueError("TimesFM-2.5 returned no point or quantile forecast values")
        median_index = 4 if quantile_values.shape[2] >= 5 else quantile_values.shape[2] // 2
        return quantile_values[:, :, median_index]

    def _forecasts_to_frame(
        self,
        forecasts: list[np.ndarray],
        entries: list[dict[str, Any]],
        task: Any,
    ) -> pd.DataFrame:
        if len(forecasts) != len(entries):
            raise ValueError(
                f"TimesFM-2.5 produced {len(forecasts)} forecasts for {len(entries)} target series"
            )

        rows: list[pd.DataFrame] = []
        horizon = _prediction_length(task)
        for entry, values in zip(entries, forecasts, strict=True):
            series = pd.Series(values).head(horizon)
            timestamps = pd.date_range(
                entry["last_timestamp"],
                periods=horizon + 1,
                freq=entry["freq"],
            )[1 : len(series) + 1]
            rows.append(
                pd.DataFrame(
                    {
                        "item_id": entry["item_id"],
                        "timestamp": timestamps,
                        "variable": entry["variable"],
                        "prediction": series.astype(float).to_numpy(),
                    }
                )
            )
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
            columns=["item_id", "timestamp", "variable", "prediction"]
        )

    def _infer_group_frequency(self, frame: pd.DataFrame) -> str:
        timestamps = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"]).drop_duplicates().sort_values())
        if len(timestamps) >= 3:
            inferred = pd.infer_freq(timestamps)
            if inferred:
                return inferred
        if len(timestamps) >= 2:
            delta = timestamps[-1] - timestamps[-2]
            offset = pd.tseries.frequencies.to_offset(delta)
            return offset.freqstr
        return "D"


@dataclass
class Toto2Adapter(BaseAdapter):
    model_id: str = "Toto-2"
    required_packages: tuple[str, ...] = ("toto-2",)
    source_url: str = "https://huggingface.co/Datadog/Toto-2.0-2.5B"
    checkpoint: str = field(default_factory=lambda: os.environ.get("TOTO2_CHECKPOINT", "Datadog/Toto-2.0-1B"))
    context_length: int = 4096
    batch_size: int = 64
    decode_block_size: int = 768
    patch_size: int = 32
    _model: Any | None = field(default=None, init=False, repr=False)
    _torch: Any | None = field(default=None, init=False, repr=False)
    _device: Any | None = field(default=None, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        if _task_value(task, "io_mode", "UV-UV") != "UV-UV":
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_io_mode",
                "Toto-2 is wired for the official Gift-Eval univariate evaluation path.",
                {"io_mode": _task_value(task, "io_mode", "UV-UV")},
            )

        target_variables = _target_variables(context_df, task)
        entries = self._context_entries(context_df, target_variables)
        if not entries:
            raise ValueError("Toto-2 received no target series to forecast")

        model, torch_module, device = self._get_model()
        forecasts: list[np.ndarray] = []
        for start in range(0, len(entries), self.batch_size):
            batch = entries[start : start + self.batch_size]
            forecasts.extend(self._forecast_batch(model, torch_module, device, batch, task))
        return self._forecasts_to_frame(forecasts, entries, task)

    def _get_model(self) -> tuple[Any, Any, Any]:
        if self._model is not None and self._torch is not None and self._device is not None:
            return self._model, self._torch, self._device
        try:
            import torch
            from toto2 import Toto2Model
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        if self.device_map == "auto":
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            device = torch.device(self.device_map)
        self._model = Toto2Model.from_pretrained(
            self.checkpoint,
            map_location=self._safetensors_device(device),
        )
        self._model = self._model.to(device).eval()
        self._torch = torch
        self._device = device
        return self._model, self._torch, self._device

    @staticmethod
    def _safetensors_device(device: Any) -> str:
        device_type = getattr(device, "type", None)
        if device_type == "cuda":
            index = getattr(device, "index", None)
            return f"cuda:{0 if index is None else index}"
        return str(device)

    def _context_entries(
        self,
        context_df: pd.DataFrame,
        target_variables: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        _require_columns(context_df, ("item_id", "timestamp", "variable", "value"))
        selected = context_df[context_df["variable"].astype(str).isin(target_variables)].copy()
        selected["timestamp"] = pd.to_datetime(selected["timestamp"])
        selected["value"] = pd.to_numeric(selected["value"], errors="raise")

        entries: list[dict[str, Any]] = []
        for (item_id, variable), group in selected.groupby(["item_id", "variable"], sort=False):
            ordered = group.sort_values("timestamp")
            target = ordered["value"].astype(float).to_numpy()[-self.context_length :]
            entries.append(
                {
                    "item_id": str(item_id),
                    "variable": str(variable),
                    "last_timestamp": pd.Timestamp(ordered["timestamp"].iloc[-1]),
                    "freq": self._infer_group_frequency(ordered),
                    "target": target,
                }
            )
        return entries

    def _forecast_batch(
        self,
        model: Any,
        torch_module: Any,
        device: Any,
        entries: list[dict[str, Any]],
        task: Any,
    ) -> list[np.ndarray]:
        horizon = _prediction_length(task)
        target_values, target_mask, has_missing_values = self._batch_arrays(entries)
        target = torch_module.tensor(target_values, dtype=torch_module.float32, device=device)
        mask = torch_module.tensor(target_mask, dtype=torch_module.bool, device=device)
        series_ids = torch_module.zeros(len(entries), 1, dtype=torch_module.long, device=device)
        with torch_module.no_grad():
            quantiles = model.forecast(
                {
                    "target": target,
                    "target_mask": mask,
                    "series_ids": series_ids,
                },
                horizon=horizon,
                decode_block_size=self.decode_block_size,
                has_missing_values=has_missing_values,
            )
        values = self._median_quantile_values(quantiles, horizon)
        return [values[index, :] for index in range(values.shape[0])]

    def _batch_arrays(self, entries: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, bool]:
        max_length = self._round_up_to_patch_multiple(max(len(entry["target"]) for entry in entries))
        target_values = np.zeros((len(entries), 1, max_length), dtype=np.float32)
        target_mask = np.zeros((len(entries), 1, max_length), dtype=bool)
        has_missing_values = False
        for index, entry in enumerate(entries):
            values = np.asarray(entry["target"], dtype=np.float32)
            finite = np.isfinite(values)
            has_missing_values = has_missing_values or not bool(finite.all())
            clean = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
            target_values[index, 0, -len(values) :] = clean
            target_mask[index, 0, -len(values) :] = finite
        return target_values, target_mask, has_missing_values

    def _round_up_to_patch_multiple(self, length: int) -> int:
        if self.patch_size <= 0:
            raise ValueError("Toto-2 patch_size must be positive")
        return ((length + self.patch_size - 1) // self.patch_size) * self.patch_size

    def _median_quantile_values(self, quantiles: Any, horizon: int) -> np.ndarray:
        if hasattr(quantiles, "detach"):
            values = quantiles.detach().cpu().numpy()
        elif hasattr(quantiles, "cpu"):
            values = quantiles.cpu().numpy()
        else:
            values = quantiles
        values = np.asarray(values, dtype=float)
        if values.ndim != 4:
            raise ValueError(f"Toto-2 returned an unsupported forecast shape: {values.shape}")
        if values.shape[0] < 5:
            median = values[values.shape[0] // 2, :, :, :]
        else:
            median = values[4, :, :, :]
        if median.shape[1] != 1:
            raise ValueError(f"Toto-2 returned multivariate forecasts for UV-UV input: {median.shape}")
        return median[:, 0, :horizon]

    def _forecasts_to_frame(
        self,
        forecasts: list[np.ndarray],
        entries: list[dict[str, Any]],
        task: Any,
    ) -> pd.DataFrame:
        if len(forecasts) != len(entries):
            raise ValueError(
                f"Toto-2 produced {len(forecasts)} forecasts for {len(entries)} target series"
            )

        rows: list[pd.DataFrame] = []
        horizon = _prediction_length(task)
        for entry, values in zip(entries, forecasts, strict=True):
            series = pd.Series(values).head(horizon)
            timestamps = pd.date_range(
                entry["last_timestamp"],
                periods=horizon + 1,
                freq=entry["freq"],
            )[1 : len(series) + 1]
            rows.append(
                pd.DataFrame(
                    {
                        "item_id": entry["item_id"],
                        "timestamp": timestamps,
                        "variable": entry["variable"],
                        "prediction": series.astype(float).to_numpy(),
                    }
                )
            )
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
            columns=["item_id", "timestamp", "variable", "prediction"]
        )

    def _infer_group_frequency(self, frame: pd.DataFrame) -> str:
        timestamps = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"]).drop_duplicates().sort_values())
        if len(timestamps) >= 3:
            inferred = pd.infer_freq(timestamps)
            if inferred:
                return inferred
        if len(timestamps) >= 2:
            delta = timestamps[-1] - timestamps[-2]
            offset = pd.tseries.frequencies.to_offset(delta)
            return offset.freqstr
        return "D"


@dataclass
class Tirex2PretrainedAdapter(BaseAdapter):
    model_id: str = "TiRex-2-Pretrained"
    required_packages: tuple[str, ...] = ("tirex-2",)
    source_url: str = "https://huggingface.co/NX-AI/TiRex-2-gifteval-pretrain"
    checkpoint: str = field(
        default_factory=lambda: os.environ.get("TIREX2_CHECKPOINT", "NX-AI/TiRex-2-gifteval-pretrain")
    )

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        if _task_value(task, "io_mode", "UV-UV") != "UV-UV":
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_io_mode",
                "TiRex-2 is registered for Gift-Eval UV-UV runs until the gated runtime API is available.",
                {"io_mode": _task_value(task, "io_mode", "UV-UV")},
            )
        try:
            __import__("tirex_2")
        except ImportError as exc:
            raise MissingDependencyError(self.model_id, self.required_packages, self.source_url, exc) from exc
        raise UnsupportedTaskError(
            self.model_id,
            "unsupported_runtime_api",
            "TiRex-2 is gated on Hugging Face and its public Python inference API was not discoverable; "
            "wire this adapter after accepting access and confirming the tirex-2 package API.",
            {"checkpoint": self.checkpoint},
        )


@dataclass
class GraniteFlowStateAdapter(BaseAdapter):
    model_id: str = "Granite-FlowState"
    required_packages: tuple[str, ...] = ("granite-tsfm", "torch")
    source_url: str = "https://huggingface.co/ibm-granite/granite-timeseries-flowstate-r1"
    checkpoint: str = field(
        default_factory=lambda: os.environ.get("FLOWSTATE_CHECKPOINT", "ibm-granite/granite-timeseries-flowstate-r1")
    )
    revision: str = field(default_factory=lambda: os.environ.get("FLOWSTATE_REVISION", "r1.1"))
    _model: Any | None = field(default=None, init=False, repr=False)
    _torch: Any | None = field(default=None, init=False, repr=False)
    _device: Any | None = field(default=None, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        if _task_value(task, "io_mode", "UV-UV") != "UV-UV":
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_io_mode",
                "FlowState currently exposes a univariate forecasting path in the Granite TSFM adapter.",
                {"io_mode": _task_value(task, "io_mode", "UV-UV")},
            )
        target_variables = _target_variables(context_df, task)
        entries = _single_series_entries(context_df, target_variables)
        if not entries:
            raise ValueError("FlowState received no target series to forecast")

        model, torch_module, device = self._get_model()
        forecasts: list[np.ndarray] = []
        horizon = _prediction_length(task)
        scale_factor = self._scale_factor(task)
        for entry in entries:
            values = torch_module.tensor(entry["target"], dtype=torch_module.float32, device=device).reshape(1, -1, 1)
            with torch_module.no_grad():
                output = model(
                    values,
                    prediction_length=horizon,
                    scale_factor=scale_factor,
                    batch_first=True,
                    return_dict=True,
                    prediction_type="median",
                )
            forecasts.append(_extract_1d_forecast(output.prediction_outputs.detach().cpu().numpy(), horizon))
        return _single_series_forecasts_to_frame(forecasts, entries, task)

    def _get_model(self) -> tuple[Any, Any, Any]:
        if self._model is not None and self._torch is not None and self._device is not None:
            return self._model, self._torch, self._device
        try:
            import torch
            from tsfm_public import FlowStateForPrediction
        except ImportError as exc:
            raise MissingDependencyError(self.model_id, self.required_packages, self.source_url, exc) from exc

        self._device = _torch_device(torch, self.device_map)
        self._torch = torch
        self._model = FlowStateForPrediction.from_pretrained(self.checkpoint, revision=self.revision).to(self._device)
        self._model.eval()
        return self._model, self._torch, self._device

    def _scale_factor(self, task: Any) -> float:
        alias = _freq_alias(task)
        mapping = {
            "10s": 10 / 3600,
            "s": 1 / 3600,
            "5min": 5 / 60,
            "10min": 10 / 60,
            "15min": 0.25,
            "30min": 0.5,
            "min": 1 / 60,
            "h": 1.0,
            "d": 3.43,
            "w": 0.46,
            "m": 2.0,
        }
        return float(mapping.get(alias, 1.0))


@dataclass
class PatchTSTFMAdapter(BaseAdapter):
    model_id: str = "PatchTST-FM"
    required_packages: tuple[str, ...] = ("granite-tsfm", "torch")
    source_url: str = "https://huggingface.co/ibm-granite/granite-timeseries-patchtst-fm-r1"
    checkpoint: str = field(
        default_factory=lambda: os.environ.get(
            "PATCHTST_FM_CHECKPOINT", "ibm-granite/granite-timeseries-patchtst-fm-r1"
        )
    )
    _model: Any | None = field(default=None, init=False, repr=False)
    _torch: Any | None = field(default=None, init=False, repr=False)
    _device: Any | None = field(default=None, init=False, repr=False)

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        if _task_value(task, "io_mode", "UV-UV") != "UV-UV":
            raise UnsupportedTaskError(
                self.model_id,
                "unsupported_io_mode",
                "PatchTST-FM is wired for Gift-Eval-style univariate zero-shot runs.",
                {"io_mode": _task_value(task, "io_mode", "UV-UV")},
            )
        target_variables = _target_variables(context_df, task)
        entries = _single_series_entries(context_df, target_variables)
        if not entries:
            raise ValueError("PatchTST-FM received no target series to forecast")

        model, torch_module, device = self._get_model()
        forecasts: list[np.ndarray] = []
        horizon = _prediction_length(task)
        for entry in entries:
            values = torch_module.tensor(entry["target"], dtype=torch_module.float32, device=device).reshape(1, -1, 1)
            with torch_module.no_grad():
                output = model(values, prediction_length=horizon, return_dict=True)
            forecasts.append(_extract_1d_forecast(output.prediction_outputs.detach().cpu().numpy(), horizon))
        return _single_series_forecasts_to_frame(forecasts, entries, task)

    def _get_model(self) -> tuple[Any, Any, Any]:
        if self._model is not None and self._torch is not None and self._device is not None:
            return self._model, self._torch, self._device
        try:
            import torch
            from tsfm_public import PatchTSTFMForPrediction
        except ImportError as exc:
            raise MissingDependencyError(self.model_id, self.required_packages, self.source_url, exc) from exc

        self._device = _torch_device(torch, self.device_map)
        self._torch = torch
        self._model = PatchTSTFMForPrediction.from_pretrained(self.checkpoint).to(self._device)
        self._model.eval()
        return self._model, self._torch, self._device
