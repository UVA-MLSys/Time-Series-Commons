# Paper 1 Benchmark Runner

This runner is for the Paper 1 zero-shot forecasting benchmark only. It does not run fine-tuning, few-shot adaptation, traditional training, leaderboard generation, or website updates.

## Scope

The first common model panel is:

- `Chronos-2`
- `TTM-R3-FT`
- `Moirai2`

Optional model records may document `Toto-2` and `TimesFM-2.5`, but they are not part of the first all-purpose three-model panel. `Toto-2` is intended for `UV-UV` and `MV-MV` only unless exogenous support changes. `TimesFM-2.5` is intended for `UV-UV` and `MV-UV`/XReg-style runs, not native `MV-MV`.

Required metadata files:

- `data/benchmark/paper1-suite.json`
- `data/benchmark/dataset-metadata.json`
- `data/benchmark/model-registry.json`

Dataset loaders expect local files. They do not download Paper 1 data.

## Install

The runner uses standard Python data tooling for planning, loading, metrics, and tests:

```bash
pip install pandas numpy pytest
```

Install model runtime packages only for the adapters you intend to execute:

```bash
pip install chronos-forecasting
pip install granite-tsfm
pip install uni2ts gluonts
```

If a model dependency is missing, the CLI writes a `skipped` result instead of fabricating forecasts.

## Dry Runs

Dry runs load the suite and print a JSON task summary. They do not load datasets or model packages.

```bash
python3 -m tools.benchmark_runner.cli \
  --suite data/benchmark/paper1-suite.json \
  --output-dir data/benchmark/runs/paper1-v0 \
  --dry-run
```

Filter flags are repeatable:

```bash
python3 -m tools.benchmark_runner.cli \
  --suite data/benchmark/paper1-suite.json \
  --output-dir data/benchmark/runs/paper1-v0 \
  --model Chronos-2 \
  --model Moirai2 \
  --dataset paper1_etth1 \
  --io-mode UV-UV \
  --horizon short \
  --dry-run
```

Use `--include-curation-required` to include suite entries that are marked as requiring curation. Without it, those tasks are filtered out during planning.

## Smoke Runs

Run a single selected task:

```bash
python3 -m tools.benchmark_runner.cli \
  --suite data/benchmark/paper1-suite.json \
  --output-dir data/benchmark/runs/paper1-v0 \
  --data-root data \
  --model Chronos-2 \
  --dataset paper1_etth1 \
  --io-mode UV-UV \
  --horizon short \
  --max-tasks 1
```

Run up to five planned tasks without changing the filters:

```bash
python3 -m tools.benchmark_runner.cli \
  --suite data/benchmark/paper1-suite.json \
  --output-dir data/benchmark/runs/paper1-v0 \
  --data-root data \
  --max-tasks 5
```

`--device-map` defaults to `auto` and is passed to model adapters. `--num-windows` defaults to `1` and controls how many chronological holdout windows are scored per task.

## Full Runs

A full zero-shot run uses the same CLI without `--dry-run` or `--max-tasks`:

```bash
python3 -m tools.benchmark_runner.cli \
  --suite data/benchmark/paper1-suite.json \
  --output-dir data/benchmark/runs/paper1-v0 \
  --data-root data
```

Use filters to expand gradually, for example ETTh1 across the common models, IO modes, and horizons:

```bash
python3 -m tools.benchmark_runner.cli \
  --suite data/benchmark/paper1-suite.json \
  --output-dir data/benchmark/runs/paper1-v0 \
  --data-root data \
  --dataset paper1_etth1
```

## Result Storage

The CLI writes one JSON result per task:

```text
data/benchmark/runs/paper1-v0/{run_id}.json
```

Each result includes:

- `schema_version`
- `benchmark_suite_id`
- `run_id`
- `dataset_id` and `tsc_dataset_id`
- `model_id`
- `io_mode`
- `evaluation_mode`, always `zero_shot`
- `horizon_id`
- `lookback_window` and `forecast_horizon`
- primary `metric`, `score`, and `higher_is_better`
- `secondary_metrics`
- `status`
- `error`
- `model_runtime`
- `features`

Status meanings:

- `completed`: the dataset loaded, the adapter produced forecasts, and the runner wrote a score.
- `skipped`: the task could not run for an expected reason, such as missing data, missing optional model dependency, required dataset curation, or unsupported model/window/frequency combination.
- `failed`: the task hit an unexpected runtime error.

Known blocked datasets:

- Traffic is marked curation-required until the source/path is resolved.
- CAMELS-US is blocked until benchmark metadata and a local data path exist.

## Non-Goals

This phase does not generate leaderboards, and it does not change `js/models.js`, `models.html`, or any website UI.
