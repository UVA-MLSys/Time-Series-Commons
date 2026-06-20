import json
from pathlib import Path

from colab.run_benchmark import (
    build_command,
    model_environment,
    prepare_run_registry,
)
from colab.run_all_benchmarks import (
    benchmark_selections,
    progress_summary,
)
from colab.setup_colab import environment_commands


def test_colab_launcher_routes_models_to_isolated_environments():
    assert model_environment("Chronos-2") == "chronos"
    assert model_environment("TTM-R3-FT") == "ttm"
    assert model_environment("Moirai2") == "moirai"


def test_colab_launcher_builds_module_command_with_filters(tmp_path):
    command = build_command(
        model_id="Chronos-2",
        benchmark_path="data/benchmark/configs/zero-shot/etth1-uv-uv.json",
        env_root=tmp_path / ".colab_venvs",
        forecast_dir="data/benchmark/forecast-artifacts",
        horizons=["short"],
        run_groups=["etth1-uv-uv"],
        num_windows=1,
        dry_run=True,
    )

    assert command[:5] == [
        str(tmp_path / ".colab_venvs/chronos/bin/python"),
        "-m",
        "tools.benchmark_runner.cli",
        "--benchmark",
        "data/benchmark/configs/zero-shot/etth1-uv-uv.json",
    ]
    assert command.count("--model") == 1
    assert "Chronos-2" in command
    assert "--horizon" in command
    assert "--run-group" in command
    assert "--dry-run" in command


def test_colab_launcher_copies_source_config_to_persistent_run_registry(tmp_path):
    source = tmp_path / "source.json"
    destination = tmp_path / "drive" / "run.json"
    source.write_text('{"results": {}}\n', encoding="utf-8")

    prepared = prepare_run_registry(source, destination)
    destination.write_text('{"results": {"completed": true}}\n', encoding="utf-8")
    prepared_again = prepare_run_registry(source, destination)

    assert prepared == destination
    assert prepared_again == destination
    assert json.loads(destination.read_text())["results"] == {"completed": True}


def test_colab_requirements_keep_conflicting_models_isolated():
    root = Path("colab/requirements")

    chronos = (root / "chronos.txt").read_text(encoding="utf-8")
    ttm = (root / "ttm.txt").read_text(encoding="utf-8")
    moirai = (root / "moirai.txt").read_text(encoding="utf-8")

    assert "chronos-forecasting" in chronos
    assert "granite-tsfm" in ttm
    assert "torch>=2.10,<2.11" in ttm
    assert "uni2ts" in moirai
    assert "torch>=2.1,<2.5" in moirai
    assert "numpy~=1.26.0" in moirai


def test_colab_setup_runs_environment_verifier_after_install(tmp_path):
    commands = environment_commands(
        "chronos",
        env_root=tmp_path / ".colab_venvs",
        requirements_dir=Path("colab/requirements"),
        python_executable="python3",
    )

    assert commands[-1][-3:] == [
        "colab/verify_environment.py",
        "--env",
        "chronos",
    ]


def test_colab_setup_bootstraps_with_virtualenv(tmp_path):
    env_root = tmp_path / ".colab_venvs"
    commands = environment_commands(
        "chronos",
        env_root=env_root,
        requirements_dir=Path("colab/requirements"),
        python_executable="python3",
    )

    assert commands[:2] == [
        ["python3", "-m", "pip", "install", "--upgrade", "virtualenv"],
        ["python3", "-m", "virtualenv", str(env_root / "chronos")],
    ]


def test_colab_notebook_is_valid_and_references_launcher():
    notebook = json.loads(Path("colab/time_series_commons_benchmark.ipynb").read_text())
    source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert "colab/setup_colab.py" in source
    assert "'colab.run_all_benchmarks'" in source
    assert "--run-registry-dir" in source
    assert "manifest.json" in source
    assert "RESET_RESULTS = False" in source
    assert "EXPECTED_REGISTRIES = 20" in source
    assert "EXPECTED_TASKS = 180" in source
    assert "assert len(config_paths) == EXPECTED_REGISTRIES" in source
    assert "assert task_count == EXPECTED_TASKS" in source
    assert "validation_args.append('--reset-run-registries')" in source


def test_full_colab_runner_skips_terminal_results_and_retries_failures():
    benchmark = {
        "runs": [
            {
                "run_group_id": "etth1-uv-uv",
                "models": ["Chronos-2", "TTM-R3-FT"],
                "horizons": ["short", "long"],
            }
        ],
        "results": {
            "etth1-uv-uv__Chronos-2__short": {"status": "completed"},
            "etth1-uv-uv__Chronos-2__long": {"status": "skipped"},
            "etth1-uv-uv__TTM-R3-FT__short": {"status": "failed"},
        },
    }

    selections = benchmark_selections(benchmark)

    assert [(item.model_id, item.horizon_ids) for item in selections] == [
        ("TTM-R3-FT", ("short", "long")),
    ]


def test_full_colab_runner_summarizes_all_registry_statuses():
    registries = [
        {
            "runs": [
                {
                    "run_group_id": "a",
                    "models": ["Chronos-2"],
                    "horizons": ["short", "long"],
                }
            ],
            "results": {
                "a__Chronos-2__short": {"status": "completed"},
            },
        },
        {
            "runs": [
                {
                    "run_group_id": "b",
                    "models": ["Moirai2"],
                    "horizons": ["short"],
                }
            ],
            "results": {
                "b__Moirai2__short": {"status": "failed"},
            },
        },
    ]

    assert progress_summary(registries) == {
        "total": 3,
        "completed": 1,
        "skipped": 0,
        "failed": 1,
        "pending": 1,
    }
