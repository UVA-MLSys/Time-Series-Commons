import pandas as pd

from .base import WideHuggingFaceDataset


class WeatherJenaDataset(WideHuggingFaceDataset):
    frequency = "10min"
    preserve_missing_values = True

    def read_raw(self):
        raw = super().read_raw()
        renames = {}
        for column in raw.columns:
            if column.startswith("SWDR ("):
                renames[column] = "SWDR (W/m2)"
            elif column.startswith("max. PAR ("):
                renames[column] = "max. PAR (umol/m2/s)"
            elif column.startswith("PAR ("):
                renames[column] = "PAR (umol/m2/s)"
        raw = raw.rename(columns=renames)
        raw[self.timestamp_column] = raw[self.timestamp_column].map(pd.Timestamp)
        raw = raw.drop_duplicates(subset=[self.timestamp_column], keep="last")
        full_index = pd.date_range(
            raw[self.timestamp_column].min(),
            raw[self.timestamp_column].max(),
            freq=self.frequency,
        )
        return (
            raw.set_index(self.timestamp_column)
            .reindex(full_index)
            .rename_axis(self.timestamp_column)
            .reset_index()
        )
