from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

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

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        raise NotImplementedError


def get_adapter(model_id: str, **kwargs: Any) -> BaseAdapter:
    adapters = {
        Chronos2Adapter.model_id: Chronos2Adapter,
        TTMAdapter.model_id: TTMAdapter,
        Moirai2Adapter.model_id: Moirai2Adapter,
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
    )
    if requested:
        return _as_tuple(requested)
    _require_columns(context_df, ("variable",))
    return tuple(dict.fromkeys(context_df["variable"].astype(str)))


def _input_variables(context_df: pd.DataFrame, task: Any) -> tuple[str, ...]:
    requested = _task_value(task, "input_variables") or _task_value(task, "variables")
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
        "10min": "10min",
        "10 min": "10min",
        "15min": "15min",
        "15 min": "15min",
        "minutely": "min",
        "minute": "min",
        "hourly": "h",
        "hour": "h",
        "daily": "d",
        "day": "d",
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
    wide = selected.pivot_table(
        index=["item_id", "timestamp"],
        columns="variable",
        values="value",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    return wide.sort_values(["item_id", "timestamp"]).reset_index(drop=True)


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

    value_columns = [column for column in target_variables if column in frame.columns]
    if value_columns:
        result = frame.melt(
            id_vars=["item_id", "timestamp"],
            value_vars=value_columns,
            var_name="variable",
            value_name="prediction",
        )
        return result.sort_values(["item_id", "variable", "timestamp"]).reset_index(drop=True)

    raise ValueError("model forecast output does not contain a point forecast column")


@dataclass
class Chronos2Adapter(BaseAdapter):
    model_id: str = "Chronos-2"
    required_packages: tuple[str, ...] = ("chronos-forecasting",)
    source_url: str = "https://github.com/amazon-science/chronos-forecasting"
    device_map: str = "auto"

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        try:
            from chronos import Chronos2Pipeline
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        target_variables = _target_variables(context_df, task)
        context, future, target_arg = self._prepare_predict_df_inputs(
            context_df, future_df, task, target_variables
        )
        pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=self.device_map)
        try:
            pred_df = pipeline.predict_df(
                context,
                future_df=future,
                prediction_length=_prediction_length(task),
                quantile_levels=[0.5],
                id_column="id",
                timestamp_column="timestamp",
                target=target_arg,
            )
        except TypeError as exc:
            if isinstance(target_arg, list):
                raise UnsupportedTaskError(
                    self.model_id,
                    "unsupported_api_version",
                    "Installed Chronos-2 predict_df does not support multiple target columns.",
                ) from exc
            raise
        return _normalize_point_forecast(pred_df, target_variables)

    def _prepare_predict_df_inputs(
        self,
        context_df: pd.DataFrame,
        future_df: pd.DataFrame | None,
        task: Any,
        target_variables: tuple[str, ...],
    ) -> tuple[pd.DataFrame, pd.DataFrame | None, str | list[str]]:
        io_mode = _task_value(task, "io_mode", "UV-UV")
        input_variables = _input_variables(context_df, task)

        if io_mode == "MV-MV" and len(target_variables) > 1:
            context = _long_to_wide(context_df, target_variables).rename(columns={"item_id": "id"})
            return context, None, list(target_variables)

        target_variable = target_variables[0]
        variables = tuple(dict.fromkeys((target_variable, *input_variables)))
        context = _long_to_wide(context_df, variables).rename(columns={"item_id": "id"})
        context = context.rename(columns={target_variable: "target"})

        future = None
        if future_df is not None and not future_df.empty:
            covariates = tuple(variable for variable in input_variables if variable != target_variable)
            if covariates:
                future = _long_to_wide(future_df, covariates).rename(columns={"item_id": "id"})
        return context, future, "target"


@dataclass
class TTMAdapter(BaseAdapter):
    model_id: str = "TTM-R3-FT"
    required_packages: tuple[str, ...] = ("granite-tsfm", "tsfm_public")
    source_url: str = "https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2"

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
        scaled, stats = self._standard_scale(context_df, target_variables)

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
        try:
            return get_model(
                model_path="ibm-granite/granite-timeseries-ttm-r2",
                context_length=_context_length(task),
                prediction_length=_prediction_length(task),
                freq=_freq_alias(task),
                return_model_key=False,
                force_return=None,
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

    def _standard_scale(
        self, context_df: pd.DataFrame, variables: tuple[str, ...]
    ) -> tuple[pd.DataFrame, dict[tuple[Any, str], tuple[float, float]]]:
        frame = context_df.copy()
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
            "context_length": _context_length(task),
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
    batch_size: int = 32

    def predict(self, context_df: pd.DataFrame, future_df: pd.DataFrame | None, task: Any) -> pd.DataFrame:
        try:
            from gluonts.dataset.pandas import PandasDataset
            from gluonts.dataset.split import split
            from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module
        except ImportError as exc:
            raise MissingDependencyError(
                self.model_id, self.required_packages, self.source_url, exc
            ) from exc

        target_variables = _target_variables(context_df, task)
        wide = _long_to_wide(context_df, target_variables).drop(columns=["item_id"])
        wide = wide.set_index("timestamp")
        dataset = PandasDataset(dict(wide))
        _, test_template = split(dataset, offset=-_context_length(task))
        test_data = test_template.generate_instances(
            prediction_length=_prediction_length(task),
            windows=1,
            distance=_prediction_length(task),
        )
        model = Moirai2Forecast(
            module=Moirai2Module.from_pretrained("Salesforce/moirai-2.0-R-small"),
            prediction_length=_prediction_length(task),
            context_length=_context_length(task),
            target_dim=1,
            feat_dynamic_real_dim=0,
            past_feat_dynamic_real_dim=0,
        )
        predictor = model.create_predictor(batch_size=self.batch_size)
        forecasts = predictor.predict(test_data.input)
        return self._forecasts_to_frame(forecasts, context_df, target_variables, task)

    def _forecasts_to_frame(
        self,
        forecasts: Iterable[Any],
        context_df: pd.DataFrame,
        target_variables: tuple[str, ...],
        task: Any,
    ) -> pd.DataFrame:
        forecast = next(iter(forecasts))
        item_id = context_df["item_id"].iloc[0]
        last_timestamp = pd.Timestamp(context_df["timestamp"].max())
        freq = pd.infer_freq(pd.DatetimeIndex(context_df["timestamp"].drop_duplicates().sort_values()))
        timestamps = pd.date_range(
            last_timestamp,
            periods=_prediction_length(task) + 1,
            freq=freq or "D",
        )[1:]

        values = None
        if hasattr(forecast, "median"):
            values = forecast.median
        elif hasattr(forecast, "mean"):
            values = forecast.mean
        elif hasattr(forecast, "quantile"):
            values = forecast.quantile(0.5)
        if values is None:
            raise ValueError("Moirai2 forecast does not expose median, mean, or quantile output")

        series = pd.Series(values).head(_prediction_length(task))
        return pd.DataFrame(
            {
                "item_id": item_id,
                "timestamp": timestamps[: len(series)],
                "variable": target_variables[0],
                "prediction": series.astype(float).to_numpy(),
            }
        )
