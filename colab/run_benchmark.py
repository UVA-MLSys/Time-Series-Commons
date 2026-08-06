from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


MODEL_TO_ENV = {
    "Chronos-2": "chronos",
    "Moirai2": "moirai",
    "TimesFM-2.5": "timesfm25",
    "Toto-2": "toto2",
    "Granite-FlowState": "flowstate",
    "PatchTST-FM": "patchtst",
}
DEFAULT_MODELS = tuple(MODEL_TO_ENV)


def model_environment(model_id: str) -> str:
    try:
        return MODEL_TO_ENV[model_id]
    except KeyError as exc:
        raise ValueError(f"Unknown Colab model environment for {model_id!r}") from exc


def build_command(
    *,
    model_id: str,
    benchmark_path: str,
    env_root: str | Path,
    forecast_dir: str,
    data_root: str = "data",
    horizons: list[str] | None = None,
    run_groups: list[str] | None = None,
    io_modes: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    num_windows: int | None = None,
    max_tasks: int | None = None,
    device_map: str = "auto",
    dry_run: bool = False,
) -> list[str]:
    env_name = model_environment(model_id)
    python_path = _env_python(Path(env_root), env_name)
    command = [
        str(python_path),
        "-m",
        "tools.benchmark_runner.cli",
        "--benchmark",
        benchmark_path,
        "--forecast-dir",
        forecast_dir,
        "--data-root",
        data_root,
        "--model",
        model_id,
        "--device-map",
        device_map,
    ]
    for value in horizons or []:
        command.extend(["--horizon", value])
    for value in run_groups or []:
        command.extend(["--run-group", value])
    for value in io_modes or []:
        command.extend(["--io-mode", value])
    for value in dataset_ids or []:
        command.extend(["--dataset", value])
    if num_windows is not None:
        command.extend(["--num-windows", str(num_windows)])
    if max_tasks is not None:
        command.extend(["--max-tasks", str(max_tasks)])
    if dry_run:
        command.append("--dry-run")
    return command


def prepare_run_registry(
    source: str | Path,
    destination: str | Path | None,
    *,
    reset: bool = False,
) -> Path:
    source_path = Path(source)
    if destination is None:
        return source_path

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if reset or not destination_path.exists():
        shutil.copy2(source_path, destination_path)
    return destination_path


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    models = args.model or list(DEFAULT_MODELS)
    benchmark_path = prepare_run_registry(
        args.benchmark,
        args.run_registry,
        reset=args.reset_run_registry,
    )
    for model_id in models:
        command = build_command(
            model_id=model_id,
            benchmark_path=str(benchmark_path),
            env_root=args.env_root,
            forecast_dir=args.forecast_dir,
            data_root=args.data_root,
            horizons=args.horizon,
            run_groups=args.run_group,
            io_modes=args.io_mode,
            dataset_ids=args.dataset,
            num_windows=args.num_windows,
            max_tasks=args.max_tasks,
            device_map=args.device_map,
            dry_run=args.dry_run,
        )
        print(" ".join(command), flush=True)
        if not args.print_commands:
            completed = subprocess.run(command, check=False)
            if completed.returncode:
                return completed.returncode
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run benchmark configs through Colab model-specific virtual environments."
    )
    parser.add_argument("--benchmark", required=True, help="Benchmark registry JSON path.")
    parser.add_argument(
        "--run-registry",
        help="Persistent registry path. The source benchmark is copied here once and this copy is updated.",
    )
    parser.add_argument(
        "--reset-run-registry",
        action="store_true",
        help="Replace an existing run registry with the source benchmark before running.",
    )
    parser.add_argument(
        "--model",
        action="append",
        choices=sorted(MODEL_TO_ENV),
        help="Model id to run. Repeat for multiple models. Defaults to all scoped models.",
    )
    parser.add_argument("--env-root", default=".colab_venvs", help="Virtual environment root.")
    parser.add_argument(
        "--forecast-dir",
        default="data/benchmark/forecast-artifacts",
        help="Directory for raw forecast Parquet artifacts.",
    )
    parser.add_argument("--data-root", default="data", help="Dataset root for local-only datasets.")
    parser.add_argument("--horizon", action="append", help="Horizon filter.")
    parser.add_argument("--run-group", action="append", help="Run group filter.")
    parser.add_argument("--io-mode", action="append", help="IO mode filter.")
    parser.add_argument("--dataset", action="append", help="Dataset id filter.")
    parser.add_argument("--num-windows", type=int, help="Override number of windows.")
    parser.add_argument("--max-tasks", type=int, help="Limit tasks per model command.")
    parser.add_argument("--device-map", default="auto", help="Model device map.")
    parser.add_argument("--dry-run", action="store_true", help="Preview tasks without inference.")
    parser.add_argument("--print-commands", action="store_true", help="Print commands without running.")
    return parser


def _env_python(env_root: Path, env_name: str) -> Path:
    if sys.platform.startswith("win"):
        return env_root / env_name / "Scripts" / "python.exe"
    return env_root / env_name / "bin" / "python"


if __name__ == "__main__":
    raise SystemExit(main())
