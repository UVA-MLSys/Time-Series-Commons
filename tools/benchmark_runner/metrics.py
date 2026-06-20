"""Forecast error metrics for Paper 1 benchmark runs."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def mae(actual: Iterable[float], predicted: Iterable[float]) -> float:
    y_true, y_pred = _validated_pair(actual, predicted)
    return float(np.mean(np.abs(y_true - y_pred)))


def mse(actual: Iterable[float], predicted: Iterable[float]) -> float:
    y_true, y_pred = _validated_pair(actual, predicted)
    return float(np.mean(np.square(y_true - y_pred)))


def rmse(actual: Iterable[float], predicted: Iterable[float]) -> float:
    return math.sqrt(mse(actual, predicted))


def smape(actual: Iterable[float], predicted: Iterable[float]) -> float:
    y_true, y_pred = _validated_pair(actual, predicted)
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    if np.any(denominator == 0.0):
        raise ValueError("sMAPE is undefined when actual and predicted are both zero")
    return float(np.mean(np.abs(y_pred - y_true) / denominator) * 100.0)


def mase(
    actual: Iterable[float],
    predicted: Iterable[float],
    *,
    insample: Iterable[float],
    seasonal_period: int,
) -> float:
    if seasonal_period < 1:
        raise ValueError("seasonal_period must be a positive integer")

    y_true, y_pred = _validated_pair(actual, predicted)
    insample_values = _as_1d_float_array(insample, "insample")
    if insample_values.size <= seasonal_period:
        raise ValueError("insample must contain more values than seasonal_period")

    naive_errors = np.abs(insample_values[seasonal_period:] - insample_values[:-seasonal_period])
    denominator = float(np.mean(naive_errors))
    if denominator == 0.0:
        raise ValueError("MASE is undefined when seasonal naive error is zero")

    return float(np.mean(np.abs(y_true - y_pred)) / denominator)


def summarize_metrics(
    actual: Iterable[float],
    predicted: Iterable[float],
    *,
    insample: Iterable[float],
    seasonal_period: int,
) -> dict[str, float]:
    return {
        "MAE": mae(actual, predicted),
        "MSE": mse(actual, predicted),
        "RMSE": rmse(actual, predicted),
        "sMAPE": smape(actual, predicted),
        "MASE": mase(
            actual,
            predicted,
            insample=insample,
            seasonal_period=seasonal_period,
        ),
    }


def _validated_pair(
    actual: Iterable[float],
    predicted: Iterable[float],
) -> tuple[np.ndarray, np.ndarray]:
    y_true = _as_1d_float_array(actual, "actual")
    y_pred = _as_1d_float_array(predicted, "predicted")
    if y_true.shape != y_pred.shape:
        raise ValueError(
            "actual and predicted must have the same shape; "
            f"got {y_true.shape} and {y_pred.shape}"
        )
    return y_true, y_pred


def _as_1d_float_array(values: Iterable[float], name: str) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array
