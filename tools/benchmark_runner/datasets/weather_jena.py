from .base import WideHuggingFaceDataset


class WeatherJenaDataset(WideHuggingFaceDataset):
    frequency = "10min"

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
        return raw.rename(columns=renames)
