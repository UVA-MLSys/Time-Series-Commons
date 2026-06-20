"""Compressed raw forecast artifact writer for benchmark runs."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd


DEFAULT_FORECAST_DIR = Path("data/benchmark/forecast-artifacts")
FORECAST_FORMAT = "parquet"
FORECAST_COMPRESSION = "zstd"


def write_forecast_artifact(
    frame: pd.DataFrame,
    task: Any,
    *,
    output_dir: str | Path = DEFAULT_FORECAST_DIR,
    started_at: str,
    base_path: str | Path | None = None,
) -> dict[str, Any]:
    """Write aligned forecast rows as compressed Parquet and return registry metadata."""

    artifact_frame = _normalize_forecast_frame(frame)
    artifact_dir = Path(output_dir) / _safe_token(task.benchmark_suite_id) / _safe_token(task.run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{_safe_token(started_at)}.parquet"

    try:
        artifact_frame.to_parquet(
            artifact_path,
            engine="pyarrow",
            compression=FORECAST_COMPRESSION,
            index=False,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Writing forecast artifacts requires pyarrow for Parquet support."
        ) from exc

    return {
        "format": FORECAST_FORMAT,
        "compression": FORECAST_COMPRESSION,
        "path": _display_path(artifact_path, base_path),
        "rows": int(len(artifact_frame)),
        "columns": list(artifact_frame.columns),
    }


def _normalize_forecast_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["window_id", "item_id", "timestamp", "variable", "actual", "prediction"]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"forecast artifact is missing required columns: {missing}")

    result = frame[columns].copy()
    result["window_id"] = result["window_id"].astype("int32")
    result["item_id"] = result["item_id"].astype(str)
    result["timestamp"] = pd.to_datetime(result["timestamp"])
    result["variable"] = result["variable"].astype(str)
    result["actual"] = result["actual"].astype("float32")
    result["prediction"] = result["prediction"].astype("float32")
    return result.sort_values(["window_id", "item_id", "variable", "timestamp"]).reset_index(
        drop=True
    )


def _safe_token(value: Any) -> str:
    token = re.sub(r"[^A-Za-z0-9_.=-]+", "_", str(value)).strip("_")
    return token or "artifact"


def _display_path(path: Path, base_path: str | Path | None) -> str:
    resolved = path.resolve()
    if base_path is not None:
        try:
            return resolved.relative_to(Path(base_path).resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()
