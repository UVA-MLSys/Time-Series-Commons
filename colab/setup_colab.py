from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ENVIRONMENTS = {
    "chronos": {
        "models": ("Chronos-2",),
        "requirements": ("common.txt", "chronos.txt"),
    },
    "moirai": {
        "models": ("Moirai2",),
        "requirements": ("common.txt", "moirai.txt"),
    },
    "timesfm25": {
        "models": ("TimesFM-2.5",),
        "requirements": ("common.txt", "timesfm.txt"),
    },
    "toto2": {
        "models": ("Toto-2",),
        "requirements": ("common.txt", "toto.txt"),
    },
    "flowstate": {
        "models": ("Granite-FlowState",),
        "requirements": ("common.txt", "flowstate.txt"),
    },
    "patchtst": {
        "models": ("PatchTST-FM",),
        "requirements": ("common.txt", "patchtst.txt"),
    },
}
MINIMUM_PYTHON = {
    "chronos": (3, 10),
    "moirai": (3, 10),
    "timesfm25": (3, 11),
    "toto2": (3, 12),
    "flowstate": (3, 10),
    "patchtst": (3, 10),
}
MODEL_TO_ENV = {
    model_id: env_name
    for env_name, config in ENVIRONMENTS.items()
    for model_id in config["models"]
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    env_names = _selected_envs(args.env, args.model)
    for env_name in env_names:
        create_environment(
            env_name,
            env_root=Path(args.env_root),
            requirements_dir=Path(args.requirements_dir),
            python_executable=args.python,
            dry_run=args.dry_run,
        )
    return 0


def create_environment(
    env_name: str,
    *,
    env_root: Path,
    requirements_dir: Path,
    python_executable: str,
    dry_run: bool = False,
) -> None:
    if env_name not in ENVIRONMENTS:
        raise ValueError(f"Unknown Colab environment: {env_name}")
    if not dry_run and sys.version_info < MINIMUM_PYTHON[env_name]:
        required = ".".join(str(value) for value in MINIMUM_PYTHON[env_name])
        raise RuntimeError(f"{env_name} requires Python {required} or newer")

    commands = environment_commands(
        env_name,
        env_root=env_root,
        requirements_dir=requirements_dir,
        python_executable=python_executable,
    )
    for command in commands:
        print(" ".join(command), flush=True)
        if not dry_run:
            subprocess.run(command, check=True)


def environment_commands(
    env_name: str,
    *,
    env_root: Path,
    requirements_dir: Path,
    python_executable: str,
) -> list[list[str]]:
    if env_name not in ENVIRONMENTS:
        raise ValueError(f"Unknown Colab environment: {env_name}")

    env_path = env_root / env_name
    env_python = str(_env_python(env_path))
    return [
        [python_executable, "-m", "pip", "install", "--upgrade", "virtualenv"],
        [python_executable, "-m", "virtualenv", str(env_path)],
        [env_python, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"],
        [
            env_python,
            "-m",
            "pip",
            "install",
            *[
                value
                for requirement in ENVIRONMENTS[env_name]["requirements"]
                for value in ("-r", str(requirements_dir / requirement))
            ],
        ],
        [env_python, "colab/verify_environment.py", "--env", env_name],
    ]


def _selected_envs(envs: list[str] | None, models: list[str] | None) -> list[str]:
    selected: list[str] = []
    if envs:
        for env_name in envs:
            selected.extend(ENVIRONMENTS if env_name == "all" else [env_name])
    if models:
        selected.extend(MODEL_TO_ENV[model_id] for model_id in models)
    if not selected:
        selected = list(ENVIRONMENTS)
    unknown = sorted(set(selected) - set(ENVIRONMENTS))
    if unknown:
        raise ValueError(f"Unknown Colab environment(s): {', '.join(unknown)}")
    return list(dict.fromkeys(selected))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create isolated Google Colab virtual environments for benchmark models."
    )
    parser.add_argument(
        "--env",
        action="append",
        choices=["all", *sorted(ENVIRONMENTS)],
        help="Environment to create. Repeat for multiple environments. Defaults to all.",
    )
    parser.add_argument(
        "--model",
        action="append",
        choices=sorted(MODEL_TO_ENV),
        help="Create the environment required by a model id.",
    )
    parser.add_argument("--env-root", default=".colab_venvs", help="Virtual environment root.")
    parser.add_argument(
        "--requirements-dir",
        default="colab/requirements",
        help="Directory containing Colab requirements files.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used for venv creation.")
    parser.add_argument("--dry-run", action="store_true", help="Print setup commands without running.")
    return parser


def _env_python(env_path: Path) -> Path:
    if sys.platform.startswith("win"):
        return env_path / "Scripts" / "python.exe"
    return env_path / "bin" / "python"


if __name__ == "__main__":
    raise SystemExit(main())
