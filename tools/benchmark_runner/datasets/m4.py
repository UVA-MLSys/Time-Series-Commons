from __future__ import annotations

from typing import Any

import pandas as pd

from .base import HuggingFaceDataset, TimeSeriesDataset


class M4Dataset(HuggingFaceDataset):
    subset: str
    frequency: str

    def read_raw(self) -> dict[str, pd.DataFrame]:
        return {
            "train": self.read_huggingface_csv("train"),
            "test": self.read_huggingface_csv("test"),
        }

    def to_dataset(self, raw: dict[str, pd.DataFrame]) -> TimeSeriesDataset:
        train = _m4_split_to_long(raw["train"], "train")
        test = _m4_split_to_long(raw["test"], "test")

        train_lengths = train.groupby("item_id")["timestamp"].max().astype(int)
        test["timestamp"] = test["timestamp"] + test["item_id"].map(train_lengths)

        values = pd.concat(
            [
                train[["item_id", "timestamp", "variable", "value"]],
                test[["item_id", "timestamp", "variable", "value"]],
            ],
            ignore_index=True,
        )
        splits = pd.concat(
            [
                train[["item_id", "timestamp", "split"]],
                test[["item_id", "timestamp", "split"]],
            ],
            ignore_index=True,
        )
        return TimeSeriesDataset(
            values=values,
            frequency=self.frequency,
            provenance=self.provenance(["train", "test"]),
            splits=splits,
        )


class M4HourlyDataset(M4Dataset):
    subset = "Hourly"
    frequency = "h"


class M4DailyDataset(M4Dataset):
    subset = "Daily"
    frequency = "D"


class M4MonthlyDataset(M4Dataset):
    subset = "Monthly"
    frequency = "MS"


def _m4_split_to_long(frame: pd.DataFrame, split: str) -> pd.DataFrame:
    if frame.empty or len(frame.columns) < 2:
        raise ValueError(f"M4 {split} file must contain a series id and at least one value column")

    item_column = frame.columns[0]
    value_columns = list(frame.columns[1:])
    stacked = (
        frame.set_index(item_column)[value_columns]
        .stack(future_stack=True)
        .dropna()
        .rename("value")
        .reset_index()
    )
    stacked.columns = ["item_id", "_step", "value"]
    step_order = {column: index + 1 for index, column in enumerate(value_columns)}
    stacked["timestamp"] = stacked["_step"].map(step_order).astype(int)
    stacked["variable"] = "y"
    stacked["split"] = split
    return stacked[["item_id", "timestamp", "variable", "value", "split"]]
