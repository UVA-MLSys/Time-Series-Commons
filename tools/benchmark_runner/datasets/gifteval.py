from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Mapping
from urllib.parse import quote

import pandas as pd
import requests

from .base import HuggingFaceDataset, TimeSeriesDataset, validate_canonical_values


@dataclass(frozen=True)
class GiftEvalRaw:
    table: Any
    dataset_info: dict[str, Any]
    dataset_path: str


class GiftEvalDataset(HuggingFaceDataset):
    """Loader for Salesforce/GiftEval Arrow datasets stored in GluonTS format."""

    source_file_key = "data"

    def __init__(
        self,
        registry_record: Mapping[str, Any],
        *,
        csv_reader=None,
        arrow_reader=None,
        info_reader=None,
    ):
        super().__init__(registry_record, csv_reader=csv_reader)
        self.arrow_reader = arrow_reader or read_arrow_table
        self.info_reader = info_reader or read_json

    @property
    def dataset_path(self) -> str:
        value = self.source["files"].get(self.source_file_key)
        if not value:
            raise ValueError("GiftEvalDataset requires source.files.data")
        return str(value).strip("/")

    def read_raw(self) -> GiftEvalRaw:
        return GiftEvalRaw(
            table=self.arrow_reader(self._gift_eval_file_url("data-00000-of-00001.arrow")),
            dataset_info=self.info_reader(self._gift_eval_file_url("dataset_info.json")),
            dataset_path=self.dataset_path,
        )

    def to_dataset(self, raw: GiftEvalRaw) -> TimeSeriesDataset:
        rows = raw.table.to_pylist()
        values: list[pd.DataFrame] = []
        static_rows: list[dict[str, Any]] = []
        gluonts_entries: list[dict[str, Any]] = []
        variables = list(self.registry_record.get("canonical_schema", {}).get("variables", []))

        for row in rows:
            item_id = str(row["item_id"])
            freq = str(row.get("freq") or self._info_frequency(raw.dataset_info) or "D")
            start = pd.Timestamp(row["start"])
            target = row["target"]
            past_feat_dynamic_real = row.get("past_feat_dynamic_real")
            if _is_multivariate_target(target):
                target_rows = list(target)
                for index, series in enumerate(target_rows):
                    variable = variables[index] if index < len(variables) else f"target[{index}]"
                    values.append(_series_to_frame(item_id, variable, start, freq, series))
                    gluonts_entries.append(
                        _gluonts_entry(
                            item_id,
                            variable,
                            start,
                            freq,
                            series,
                            past_feat_dynamic_real=past_feat_dynamic_real,
                        )
                    )
                    static_rows.append({"item_id": item_id, "variable": variable, "gift_eval_dim": index})
            else:
                variable = variables[0] if variables else "target"
                values.append(_series_to_frame(item_id, variable, start, freq, target))
                gluonts_entries.append(
                    _gluonts_entry(
                        item_id,
                        variable,
                        start,
                        freq,
                        target,
                        past_feat_dynamic_real=past_feat_dynamic_real,
                    )
                )
                static_rows.append({"item_id": item_id, "variable": variable})

        value_frame = (
            pd.concat(values, ignore_index=True)
            if values
            else pd.DataFrame(columns=["item_id", "timestamp", "variable", "value"])
        )
        static_features = pd.DataFrame(static_rows).drop_duplicates().reset_index(drop=True) if static_rows else None
        return TimeSeriesDataset(
            values=validate_canonical_values(value_frame),
            frequency=_normalize_frequency(rows[0].get("freq") if rows else self.registry_record.get("frequency", {}).get("recorded_frequency", "D")),
            provenance=self.provenance([self.source_file_key])
            | {
                "source_format": "gift_eval_arrow",
                "gift_eval_dataset": raw.dataset_path,
                "gift_eval_target_ndim": _target_ndim_from_info(raw.dataset_info),
                "gift_eval_target_dim": _target_dim_from_info(raw.dataset_info),
            },
            static_features=static_features,
            gluonts_entries=gluonts_entries,
        )

    def _gift_eval_file_url(self, filename: str) -> str:
        repo_id = quote(str(self.source["repo_id"]), safe="/")
        revision = quote(str(self.source["revision"]), safe="")
        path = quote(f"{self.dataset_path}/{filename}", safe="/")
        return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{path}"

    def _info_frequency(self, dataset_info: dict[str, Any]) -> str | None:
        name = str(dataset_info.get("dataset_name", ""))
        if "/" in name:
            maybe_freq = name.rsplit("/", 1)[-1]
            if maybe_freq:
                return maybe_freq
        return None


def read_arrow_table(url: str):
    try:
        import pyarrow.ipc as ipc
    except ImportError as exc:
        raise ImportError("GiftEvalDataset requires pyarrow to read Arrow files") from exc

    with requests.get(url, stream=True, timeout=(10, 240)) as response:
        response.raise_for_status()
        payload = BytesIO(response.content)
    try:
        with ipc.open_stream(payload) as reader:
            return reader.read_all()
    except Exception:
        payload.seek(0)
        with ipc.open_file(payload) as reader:
            return reader.read_all()


def read_json(url: str) -> dict[str, Any]:
    with requests.get(url, timeout=(10, 60)) as response:
        response.raise_for_status()
        return response.json()


def _series_to_frame(item_id: str, variable: str, start: pd.Timestamp, freq: str, series: Any) -> pd.DataFrame:
    values = list(series)
    timestamps = pd.date_range(start=start, periods=len(values), freq=_normalize_frequency(freq))
    return pd.DataFrame(
        {
            "item_id": item_id,
            "timestamp": timestamps,
            "variable": variable,
            "value": values,
        }
    )


def _gluonts_entry(
    item_id: str,
    variable: str,
    start: pd.Timestamp,
    freq: str,
    series: Any,
    *,
    past_feat_dynamic_real: Any = None,
) -> dict[str, Any]:
    encoded_item_id = f"{item_id}\u001f{variable}"
    entry = {
        "item_id": encoded_item_id,
        "tsc_item_id": item_id,
        "tsc_variable": variable,
        "start": pd.Period(start, freq=_normalize_frequency(freq)),
        "target": list(series),
    }
    if past_feat_dynamic_real is not None:
        entry["past_feat_dynamic_real"] = past_feat_dynamic_real
    return entry


def _is_multivariate_target(target: Any) -> bool:
    if target is None or len(target) == 0:
        return False
    return isinstance(target[0], (list, tuple))


def _normalize_frequency(freq: Any) -> str:
    freq = str(freq or "D")
    return {"min": "T", "h": "H"}.get(freq, freq)


def _target_ndim_from_info(dataset_info: dict[str, Any]) -> int:
    target = dataset_info.get("features", {}).get("target", {})
    feature = target.get("feature")
    if isinstance(feature, dict) and feature.get("_type") == "Sequence":
        return 2
    return 1


def _target_dim_from_info(dataset_info: dict[str, Any]) -> int:
    target = dataset_info.get("features", {}).get("target", {})
    if "length" in target:
        return int(target["length"])
    return 1
