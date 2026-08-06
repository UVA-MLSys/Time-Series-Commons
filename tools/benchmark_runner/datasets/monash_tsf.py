from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import zipfile
from typing import Any

import pandas as pd
import requests

from .base import HuggingFaceDataset, TimeSeriesDataset, validate_canonical_values


@dataclass(frozen=True)
class TsfRow:
    attributes: dict[str, str]
    values: list[float | None]


@dataclass(frozen=True)
class TsfFile:
    relation: str | None
    attributes: list[str]
    frequency: str
    missing: bool
    equal_length: bool
    rows: list[TsfRow]


class MonashTsfDataset(HuggingFaceDataset):
    """Loader for Monash archive TSF files stored as HF zip artifacts."""

    source_file_key = "data"
    target_variable = "y"

    def __init__(self, registry_record, *, tsf_reader=None, csv_reader=None):
        super().__init__(registry_record, csv_reader=csv_reader)
        self.tsf_reader = tsf_reader or read_huggingface_tsf_zip

    def read_raw(self) -> TsfFile:
        return parse_tsf(self.tsf_reader(self.file_url(self.source_file_key)))

    def to_dataset(self, raw: TsfFile) -> TimeSeriesDataset:
        frequency = frequency_to_pandas(raw.frequency)
        frames = []
        static_rows = []
        for row in raw.rows:
            item_id = self.row_item_id(row.attributes)
            variable = self.row_variable(row.attributes)
            start = parse_tsf_timestamp(row.attributes["start_timestamp"])
            timestamps = pd.date_range(start=start, periods=len(row.values), freq=frequency)
            frame = pd.DataFrame(
                {
                    "item_id": item_id,
                    "timestamp": timestamps,
                    "variable": variable,
                    "value": row.values,
                }
            ).dropna(subset=["value"])
            frames.append(frame)
            static_rows.append(self.row_static_features(row.attributes, item_id, variable))

        values = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["item_id", "timestamp", "variable", "value"])
        static = pd.DataFrame(static_rows).drop_duplicates().reset_index(drop=True) if static_rows else None
        return TimeSeriesDataset(
            values=validate_canonical_values(values),
            frequency=frequency,
            provenance=self.provenance([self.source_file_key]) | {
                "source_format": "monash_tsf_zip",
                "relation": raw.relation,
                "tsf_frequency": raw.frequency,
                "missing": raw.missing,
                "equal_length": raw.equal_length,
            },
            static_features=static,
        )

    def row_item_id(self, attributes: dict[str, str]) -> str:
        return attributes.get("series_name", self.item_id)

    def row_variable(self, attributes: dict[str, str]) -> str:
        return self.target_variable

    def row_static_features(self, attributes: dict[str, str], item_id: str, variable: str) -> dict[str, Any]:
        ignored = {"start_timestamp"}
        features = {key: value for key, value in attributes.items() if key not in ignored}
        return {"item_id": item_id, "variable": variable, **features}


class TemperatureRainDataset(MonashTsfDataset):
    def row_item_id(self, attributes: dict[str, str]) -> str:
        return attributes["station_id"]

    def row_variable(self, attributes: dict[str, str]) -> str:
        return attributes["obs_or_fcst"]


class KddCup2018Dataset(MonashTsfDataset):
    def row_item_id(self, attributes: dict[str, str]) -> str:
        return f"{attributes['city']}/{attributes['station']}"

    def row_variable(self, attributes: dict[str, str]) -> str:
        return attributes["air_quality_measurement"]


class USBirthsDataset(MonashTsfDataset):
    target_variable = "daily_us_births"


class SaugeenDayDataset(MonashTsfDataset):
    target_variable = "daily_mean_river_flow_cms"


class CovidDeathsDataset(MonashTsfDataset):
    target_variable = "daily_covid_deaths"


def read_huggingface_tsf_zip(url: str) -> str:
    with requests.get(url, stream=True, timeout=(10, 240)) as response:
        response.raise_for_status()
        payload = response.content
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        tsf_names = [name for name in archive.namelist() if name.lower().endswith(".tsf")]
        if len(tsf_names) != 1:
            raise ValueError(f"Expected one .tsf file in Monash archive, found {len(tsf_names)}")
        return archive.read(tsf_names[0]).decode("utf-8")


def parse_tsf(text: str) -> TsfFile:
    relation = None
    attributes: list[str] = []
    frequency = "unknown"
    missing = False
    equal_length = False
    rows: list[TsfRow] = []
    in_data = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lower = line.lower()
        if not in_data:
            if lower.startswith("@relation"):
                relation = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) == 2 else None
            elif lower.startswith("@attribute"):
                parts = line.split()
                if len(parts) < 3:
                    raise ValueError(f"Invalid TSF attribute line: {line}")
                attributes.append(parts[1])
            elif lower.startswith("@frequency"):
                frequency = line.split(maxsplit=1)[1].strip().lower()
            elif lower.startswith("@missing"):
                missing = _parse_bool_directive(line)
            elif lower.startswith("@equallength"):
                equal_length = _parse_bool_directive(line)
            elif lower == "@data":
                if not attributes:
                    raise ValueError("TSF file declares @data before any @attribute lines")
                in_data = True
            continue

        parts = line.split(":", len(attributes))
        if len(parts) != len(attributes) + 1:
            raise ValueError(f"TSF data row has {len(parts) - 1} attributes; expected {len(attributes)}")
        row_attributes = dict(zip(attributes, parts[:-1]))
        rows.append(TsfRow(row_attributes, [_parse_tsf_value(value) for value in parts[-1].split(",")]))

    if not in_data:
        raise ValueError("TSF file is missing @data")
    return TsfFile(relation, attributes, frequency, missing, equal_length, rows)


def frequency_to_pandas(frequency: str) -> str:
    mapping = {
        "daily": "D",
        "hourly": "h",
        "weekly": "W",
        "monthly": "MS",
        "quarterly": "QS",
        "yearly": "YS",
    }
    try:
        return mapping[frequency.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported Monash TSF frequency: {frequency}") from exc


def parse_tsf_timestamp(value: str) -> pd.Timestamp:
    value = value.strip()
    if " " not in value:
        return pd.Timestamp(value)
    date, time = value.split(maxsplit=1)
    return pd.Timestamp(f"{date} {time.replace('-', ':')}")


def _parse_tsf_value(value: str) -> float | None:
    value = value.strip()
    if value in {"", "?"}:
        return None
    return float(value)


def _parse_bool_directive(line: str) -> bool:
    parts = line.split(maxsplit=1)
    return len(parts) == 2 and parts[1].strip().lower() == "true"
