from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Iterable

from tools.benchmark_runner.benchmark_registry import record_result, validate_benchmark
from tools.benchmark_runner.cli import _run_task
from tools.benchmark_runner.generate_gifteval_zero_shot_configs import gift_eval_config_names
from tools.benchmark_runner.metadata import generate_tasks, load_suite


MODEL_ID = "Chronos-2"
TERMINAL_STATUSES = {"completed"}
GIFT_EVAL_CONFIG_NAMES = gift_eval_config_names()


@dataclass(frozen=True)
class RunSummary:
    total: int
    completed: int
    skipped: int
    failed: int
    pending: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "completed": self.completed,
            "skipped": self.skipped,
            "failed": self.failed,
            "pending": self.pending,
        }


def prepare_run_registries(
    *,
    config_dir: str | Path,
    run_registry_dir: str | Path,
    reset: bool = False,
    model_id: str = MODEL_ID,
) -> list[Path]:
    source_dir = Path(config_dir)
    destination_dir = Path(run_registry_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    registry_paths: list[Path] = []
    for name in GIFT_EVAL_CONFIG_NAMES:
        source = source_dir / name
        destination = destination_dir / name
        if reset or not destination.exists():
            shutil.copy2(source, destination)
        ensure_model_in_registry(destination, model_id=model_id)
        registry_paths.append(destination)
    return registry_paths


def ensure_model_in_registry(path: str | Path, *, model_id: str) -> None:
    """Ensure a model-specific Colab run can use a shared Gift-Eval registry."""

    registry_path = Path(path)
    benchmark = load_suite(registry_path)
    changed = False

    if benchmark.get("schema_version") == "0.2.0":
        model_profiles = benchmark.setdefault("model_profiles", {})
        if model_id not in model_profiles:
            model_profiles[model_id] = "default"
            changed = True
        for run in benchmark.get("runs", []):
            models = run.setdefault("models", [])
            if model_id not in models:
                models.append(model_id)
                changed = True
    else:
        models = benchmark.setdefault("models", [])
        if model_id not in models:
            models.append(model_id)
            changed = True

    if changed:
        registry_path.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")


def validate_run_registries(
    registry_paths: Iterable[str | Path],
    *,
    model_id: str = MODEL_ID,
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for path in registry_paths:
        registry_path = Path(path)
        benchmark = load_suite(registry_path)
        validate_benchmark(benchmark)
        tasks = generate_tasks(benchmark, model_ids=[model_id])
        if not tasks:
            raise ValueError(f"No {model_id} tasks generated for {registry_path}")
        bad_context = sorted({task.context_policy for task in tasks} - {"full_history"})
        bad_source = sorted({task.source_benchmark for task in tasks} - {"gift_eval"})
        if bad_context or bad_source:
            raise ValueError(
                f"{registry_path} is not a strict Gift-Eval window registry: "
                f"context={bad_context}, source={bad_source}"
            )
        summaries[registry_path.name] = {
            "tasks": len(tasks),
            "windows": sorted({task.window_id or task.horizon_id for task in tasks}),
            "forecast_horizons": sorted({task.forecast_horizon for task in tasks}),
            "io_modes": sorted({task.io_mode for task in tasks}),
        }
    return summaries


def progress_summary(
    registry_paths: Iterable[str | Path],
    *,
    model_id: str = MODEL_ID,
) -> RunSummary:
    total = 0
    statuses: Counter[str] = Counter()
    for path in registry_paths:
        benchmark = load_suite(path)
        results = benchmark.get("results", {})
        for task in generate_tasks(benchmark, model_ids=[model_id]):
            total += 1
            result = results.get(task.run_id)
            statuses[str(result.get("status")) if result else "pending"] += 1
    return RunSummary(
        total=total,
        completed=statuses["completed"],
        skipped=statuses["skipped"],
        failed=statuses["failed"],
        pending=total - statuses["completed"] - statuses["skipped"] - statuses["failed"],
    )

def _gift_eval_registry_paths(run_registry_dir: str | Path) -> list[Path]:
    root = Path(run_registry_dir)
    paths = [root / name for name in GIFT_EVAL_CONFIG_NAMES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing Gift-Eval run registry file(s): " + ", ".join(missing)
        )
    return paths


def run_gifteval_model(
    *,
    model_id: str,
    run_registry_dir: str | Path,
    data_root: str | Path = "data",
    device_map: str = "auto",
    max_tasks: int | None = None,
) -> RunSummary:
    registry_paths = _gift_eval_registry_paths(run_registry_dir)
    args = argparse.Namespace(
        data_root=str(data_root),
        device_map=device_map,
        num_windows=None,
        adapter_cache={},
    )
    launched = 0
    for registry_path in registry_paths:
        benchmark = load_suite(registry_path)
        validate_benchmark(benchmark)
        results = benchmark.get("results", {})
        for task in generate_tasks(benchmark, model_ids=[model_id]):
            if max_tasks is not None and launched >= max_tasks:
                return write_manifest(
                    registry_paths,
                    Path(run_registry_dir) / "manifest.json",
                    model_id=model_id,
                )
            if results.get(task.run_id, {}).get("status") in TERMINAL_STATUSES:
                continue
            print(f"Running {task.run_id}", flush=True)
            result = _run_task(task, benchmark, args)
            record_result(registry_path, result)
            _release_task_runtime(args, task.model_id)
            launched += 1
            benchmark = load_suite(registry_path)
            results = benchmark.get("results", {})
            write_manifest(
                registry_paths,
                Path(run_registry_dir) / "manifest.json",
                model_id=model_id,
            )
    return write_manifest(
        registry_paths,
        Path(run_registry_dir) / "manifest.json",
        model_id=model_id,
    )


def run_chronos2_gifteval(
    *,
    run_registry_dir: str | Path,
    data_root: str | Path = "data",
    device_map: str = "auto",
    max_tasks: int | None = None,
) -> RunSummary:
    return run_gifteval_model(
        model_id=MODEL_ID,
        run_registry_dir=run_registry_dir,
        data_root=data_root,
        device_map=device_map,
        max_tasks=max_tasks,
    )


def write_manifest(
    registry_paths: Iterable[str | Path],
    manifest_path: str | Path,
    *,
    model_id: str = MODEL_ID,
) -> RunSummary:
    summary = progress_summary(registry_paths, model_id=model_id)
    manifest = {
        "schema_version": "0.1.0",
        "model_id": model_id,
        "window_standard": "gift_eval",
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registries": [Path(path).name for path in registry_paths],
        "progress": summary.to_dict(),
    }
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one model on Gift-Eval-overlap registries.")
    parser.add_argument("--config-dir", default="data/benchmark/configs/zero-shot")
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--run-registry-dir", required=True)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--reset-run-registries", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    registries = prepare_run_registries(
        config_dir=args.config_dir,
        run_registry_dir=args.run_registry_dir,
        reset=args.reset_run_registries,
        model_id=args.model_id,
    )
    validation = validate_run_registries(registries, model_id=args.model_id)
    print(json.dumps(validation, indent=2), flush=True)
    if args.dry_run:
        summary = write_manifest(
            registries,
            Path(args.run_registry_dir) / "manifest.json",
            model_id=args.model_id,
        )
        print(json.dumps(summary.to_dict(), indent=2), flush=True)
        return 0
    summary = run_gifteval_model(
        model_id=args.model_id,
        run_registry_dir=args.run_registry_dir,
        data_root=args.data_root,
        device_map=args.device_map,
        max_tasks=args.max_tasks,
    )
    print(json.dumps(summary.to_dict(), indent=2), flush=True)
    return 0


def _release_task_runtime(args: argparse.Namespace, model_id: str) -> None:
    if model_id not in {
        "Moirai2",
        "Toto-2",
        "Granite-FlowState",
        "PatchTST-FM",
    }:
        return
    cache = getattr(args, "adapter_cache", None)
    if isinstance(cache, dict):
        cache.clear()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
