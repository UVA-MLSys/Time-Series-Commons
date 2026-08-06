from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from colab.run_benchmark import build_command, prepare_run_registry


TERMINAL_STATUSES = {"completed", "skipped"}


@dataclass(frozen=True)
class BenchmarkSelection:
    run_group_id: str
    model_id: str
    horizon_ids: tuple[str, ...]


def benchmark_selections(benchmark: dict[str, Any]) -> list[BenchmarkSelection]:
    results = benchmark.get("results", {})
    selections: list[BenchmarkSelection] = []
    for run in benchmark.get("runs", []):
        run_group_id = str(run["run_group_id"])
        for model_id in run.get("models", []):
            pending_horizons = tuple(
                str(window_id)
                for window_id in _run_window_ids(run)
                if results.get(
                    _run_id(run_group_id, str(model_id), str(window_id)), {}
                ).get("status")
                not in TERMINAL_STATUSES
            )
            if pending_horizons:
                selections.append(
                    BenchmarkSelection(
                        run_group_id=run_group_id,
                        model_id=str(model_id),
                        horizon_ids=pending_horizons,
                    )
                )
    return selections


def progress_summary(registries: Iterable[dict[str, Any]]) -> dict[str, int]:
    total = 0
    statuses: Counter[str] = Counter()
    for benchmark in registries:
        results = benchmark.get("results", {})
        for run in benchmark.get("runs", []):
            run_group_id = str(run["run_group_id"])
            for model_id in run.get("models", []):
                for horizon_id in _run_window_ids(run):
                    total += 1
                    result = results.get(
                        _run_id(run_group_id, str(model_id), str(horizon_id))
                    )
                    statuses[str(result.get("status")) if result else "pending"] += 1
    return {
        "total": total,
        "completed": statuses["completed"],
        "skipped": statuses["skipped"],
        "failed": statuses["failed"],
        "pending": total
        - statuses["completed"]
        - statuses["skipped"]
        - statuses["failed"],
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_paths = sorted(Path(args.config_dir).glob("*.json"))
    if not config_paths:
        raise SystemExit(f"No benchmark configs found in {args.config_dir}")

    registry_dir = Path(args.run_registry_dir)
    registry_paths = [
        prepare_run_registry(
            config_path,
            registry_dir / config_path.name,
            reset=args.reset_run_registries,
        )
        for config_path in config_paths
    ]
    _write_manifest(registry_paths, registry_dir / "manifest.json")

    launcher_failures = 0
    for registry_path in registry_paths:
        benchmark = _read_json(registry_path)
        for selection in benchmark_selections(benchmark):
            command = build_command(
                model_id=selection.model_id,
                benchmark_path=str(registry_path),
                env_root=args.env_root,
                forecast_dir=args.forecast_dir,
                data_root=args.data_root,
                horizons=list(selection.horizon_ids),
                run_groups=[selection.run_group_id],
                num_windows=args.num_windows,
                device_map=args.device_map,
                dry_run=args.dry_run,
            )
            print(" ".join(command), flush=True)
            if not args.print_commands:
                completed = subprocess.run(command, check=False)
                if completed.returncode:
                    launcher_failures += 1
            _write_manifest(registry_paths, registry_dir / "manifest.json")

    summary = _write_manifest(registry_paths, registry_dir / "manifest.json")
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 1 if launcher_failures else 0


def _write_manifest(
    registry_paths: Iterable[Path],
    manifest_path: Path,
) -> dict[str, Any]:
    paths = list(registry_paths)
    registries = [_read_json(path) for path in paths]
    summary: dict[str, Any] = {
        "schema_version": "0.1.0",
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registries": [path.name for path in paths],
        "progress": progress_summary(registries),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(manifest_path)
    return summary


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_id(run_group_id: str, model_id: str, horizon_id: str) -> str:
    return f"{run_group_id}__{model_id}__{horizon_id}"


def _run_window_ids(run: dict[str, Any]) -> list[str]:
    return [str(value) for value in run.get("evaluation_windows", run.get("horizons", []))]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or resume every zero-shot benchmark config in Google Colab."
    )
    parser.add_argument(
        "--config-dir",
        default="data/benchmark/configs/zero-shot",
        help="Directory containing source benchmark JSON configs.",
    )
    parser.add_argument(
        "--run-registry-dir",
        required=True,
        help="Persistent directory for writable result registry JSON files.",
    )
    parser.add_argument(
        "--forecast-dir",
        required=True,
        help="Persistent directory for raw forecast Parquet artifacts.",
    )
    parser.add_argument("--env-root", default=".colab_venvs")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--num-windows", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-commands", action="store_true")
    parser.add_argument("--reset-run-registries", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
