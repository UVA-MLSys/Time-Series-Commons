"""Dataset contracts, loaders, and compatibility helpers."""

from .base import (
    NORMALIZED_COLUMNS,
    BaseDataset,
    DatasetUnavailableError,
    HuggingFaceDataset,
    InsufficientDataError,
    TimeSeriesDataset,
    build_windows,
    load_dataset_for_task,
    load_dataset_object_for_task,
    validate_canonical_values,
    validate_task_window,
    wide_csv_to_long,
)

__all__ = [
    "NORMALIZED_COLUMNS",
    "BaseDataset",
    "DatasetUnavailableError",
    "HuggingFaceDataset",
    "InsufficientDataError",
    "TimeSeriesDataset",
    "build_windows",
    "load_dataset_for_task",
    "load_dataset_object_for_task",
    "validate_canonical_values",
    "validate_task_window",
    "wide_csv_to_long",
]

