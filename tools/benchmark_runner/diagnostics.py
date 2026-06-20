from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def summarize_registry_dir(path: str | Path) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for registry_path in sorted(Path(path).glob("*.json")):
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(payload.get("runs"), list):
            runs.extend(payload["runs"])
        elif "status" in payload:
            runs.append(payload)

    totals = Counter(str(run.get("status", "unknown")) for run in runs)
    failure_groups = Counter()
    for run in runs:
        if run.get("status") != "failed":
            continue
        error = run.get("error") or {}
        message = str(error.get("message", ""))
        key = (
            str(run.get("model_id")),
            str(run.get("io_mode")),
            str(error.get("type") or error.get("reason") or "unknown"),
            message[:120],
        )
        failure_groups[key] += 1

    return {
        "totals": dict(sorted(totals.items())),
        "failure_groups": [
            {
                "count": count,
                "model_id": model_id,
                "io_mode": io_mode,
                "error_type": error_type,
                "message_prefix": message_prefix,
            }
            for (model_id, io_mode, error_type, message_prefix), count in sorted(
                failure_groups.items()
            )
        ],
    }
