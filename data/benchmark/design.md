# Time Series Commons Benchmark Design

This document is the compact design reference for benchmark execution, result storage, leaderboard generation, and future agent-based model recommendation.

## Goal

The benchmark layer should support configurable forecasting experiments across heterogeneous time series datasets and models. Datasets may arrive in different formats, and models may be foundation models used zero-shot or traditional/deep-learning models that require training. The first benchmark pass uses default model hyperparameters only.

The benchmark system should produce JSON artifacts that can drive:

- global leaderboards
- dataset-specific leaderboards
- taxonomy/category leaderboards
- IO-mode and evaluation-mode comparisons
- future agent recommendations based on similar completed runs

## Existing Metadata Layers

`data/models.json` remains the website catalog. Its top-level `models` array currently stores dataset records, and each dataset has a `benchmarks` object that indicates whether the dataset is associated with a model, library, benchmark, or source. Do not store benchmark scores in this file.

`data/benchmark/dataset-metadata.json` is the dataset eligibility layer. It stores:

- `dataset_id`
- `benchmark_ready`
- taxonomy labels
- supported `io_modes`
- supported `evaluation_modes`
- frequency and shape
- recommended metrics

`data/benchmark/model-registry.json` is the model eligibility layer. It stores:

- `model_id`, matching current website model keys exactly
- `model_type`: `foundation` or `traditional`
- supported `evaluation_modes`
- supported `io_modes`
- `source_link`

Benchmark code should select runnable tasks by intersecting dataset and model capabilities.

## Run-Only First Design

For the first implementation, benchmark runs should be self-contained JSON files under:

```text
data/benchmark/runs/
```

A separate benchmark plan is useful later for reproducibility and missing-run accounting, but it is not required for recommendations if every run result records enough context.

Recommended example path:

```text
data/benchmark/runs/examples/example-run-result.json
```

## Run Result Schema

Each JSON file should represent one atomic benchmark run:

```text
dataset_id + model_id + io_mode + evaluation_mode + lookback_window + forecast_horizon + split_id
```

Recommended fields:

```json
{
  "schema_version": "0.1.0",
  "benchmark_suite_id": "poc-v0",
  "run_id": "poc-v0__ETTh1__TimesNet__MV-MV__h336__traditional_training__standard",

  "dataset_id": "ETTh1",
  "model_id": "TimesNet",
  "model_type": "traditional",
  "io_mode": "MV-MV",
  "evaluation_mode": "traditional_training",

  "lookback_window": 720,
  "forecast_horizon": 336,
  "split_id": "standard",
  "metric": "MAE",

  "features": {
    "observed_streams": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
    "target_streams": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
    "exogenous_streams": [],
    "exogenous_static_variables": []
  },

  "status": "completed",
  "score": 0.391,
  "higher_is_better": false,

  "secondary_metrics": {
    "MSE": 0.284,
    "RMSE": 0.533
  },

  "relative_score": 0.82,
  "baseline_model_id": "Naive",
  "baseline_score": 0.477,

  "dataset_taxonomy": [
    "Regularly sampled",
    "Pure temporal",
    "Non-stationary",
    "Non-linear/stochastic",
    "Pure numerical"
  ],

  "error": null
}
```

Feature labels mean:

- `observed_streams`: time-dependent variables available from past/current time.
- `target_streams`: future variables being predicted.
- `exogenous_streams`: supporting time-dependent inputs beyond the target streams.
- `exogenous_static_variables`: non-time-varying features such as location, basin properties, item metadata, or hierarchy attributes.

Examples:

```json
{
  "features": {
    "observed_streams": ["streamflow"],
    "target_streams": ["streamflow"],
    "exogenous_streams": [],
    "exogenous_static_variables": []
  }
}
```

```json
{
  "features": {
    "observed_streams": ["streamflow", "precipitation", "temperature", "pet"],
    "target_streams": ["streamflow"],
    "exogenous_streams": ["precipitation", "temperature", "pet"],
    "exogenous_static_variables": ["basin_area", "elevation", "soil_depth", "forest_fraction"]
  }
}
```

`status` should be one of:

- `completed`
- `failed`
- `skipped`

For failed or skipped runs, keep the same identifying fields and set:

```json
{
  "status": "skipped",
  "score": null,
  "error": {
    "reason": "ineligible_io_mode",
    "message": "Dataset and model do not both support MV-MV."
  }
}
```

## Eligibility Rules

A run is eligible only if all of these hold:

```text
dataset.benchmark_ready == true
io_mode in dataset.capabilities.io_modes
io_mode in model.io_modes
evaluation_mode in dataset.capabilities.evaluation_modes
evaluation_mode in model.evaluation_modes
dataset has enough history for lookback_window + forecast_horizon
```

This means the runner should generate candidate tasks from metadata, then skip or omit ineligible tasks with a reason.

## IO Modes

Use exactly these IO modes:

- `UV-UV`: one input series predicts the same or another single target series
- `MV-UV`: multiple synchronized input variables predict one target variable
- `MV-MV`: multiple synchronized input variables predict multiple output variables

Do not force MV modes when the dataset streams are independent. For examples such as M4 or many intermittent-demand SKU collections, UV-UV may be the only recommended mode unless there are meaningful covariates, hierarchy, or item metadata.

## Evaluation Modes

Use exactly these evaluation modes:

- `zero_shot`: no dataset-specific training
- `fine_tuned`: pretrained/foundation model adapted on the training split
- `traditional_training`: model trained from scratch or through a standard library training path

## Initial Horizon Grid

Recent long-term forecasting benchmarks commonly report horizons `96`, `192`, `336`, and `720` on ETT, ECL, Traffic, Weather, and related datasets. For the first TSC pass, start with three required profiles and keep the fourth optional:

| horizon_id | lookback_window | forecast_horizon | Use |
| --- | ---: | ---: | --- |
| short | 96 | 96 | Paper-comparable starter setting |
| medium | 336 | 192 | More context with moderate runtime |
| long | 720 | 336 | Long-context stress test |
| extra_long | 720 | 720 | Optional, after the runner is stable |

Frequency-aware overrides should be used for low-frequency datasets:

| Frequency | Short | Medium | Long |
| --- | --- | --- | --- |
| Hourly | `96 -> 96` | `336 -> 192` | `720 -> 336` |
| Daily | `90 -> 30` | `365 -> 90` | `730 -> 180` |
| Weekly | `104 -> 24` | `156 -> 36` | `208 -> 48` |
| Monthly | `36 -> 12` | `60 -> 18` | `84 -> 24` |

For early experiments, prioritize `short`, `medium`, and `long`. Add `extra_long` only when runtime and dataset length allow it.

## Ranking Policy

Do not compare raw MAE, MSE, or RMSE across unrelated datasets as a global score. Use one of:

- per-task rank aggregation
- baseline-relative score
- normalized error within each dataset/config

Every leaderboard should show coverage:

```text
completed_runs / eligible_runs
```

This prevents a model from ranking highly only because it ran on easier datasets or fewer tasks.

## Recommendation Agent Use

A future recommendation agent should retrieve related completed runs by:

- dataset taxonomy
- domain
- frequency
- IO mode
- evaluation mode
- forecast horizon
- model type
- primary metric and relative score

The run result JSON should be self-contained enough for recommendations even if a separate benchmark plan is absent.

Recommended recommendation behavior:

1. Filter runs to the requested dataset/task shape.
2. Prefer models with high relative score and broad coverage.
3. Penalize or caveat models with sparse evidence.
4. Distinguish `no run found` from `model/dataset ineligible` when metadata allows.

## Benchmark Anchors

Recent benchmark practice to mirror:

- PatchTST, iTransformer, TimesNet, and TimeMixer commonly use ETT, ECL/Electricity, Traffic, Weather, Exchange, and horizons such as `96`, `192`, `336`, `720`.
- Foundation-model evaluations such as Chronos, TimesFM, Moirai, TTM, Time-MOE, and GIFT-Eval emphasize zero-shot evaluation, broad dataset coverage, and leakage-aware reporting.
- M4 and Monash-style benchmarks emphasize frequency-specific horizons and scaled/relative metrics such as MASE, sMAPE, OWA, or baseline-relative scoring.

## Implementation Notes

The runner should be adapter-based:

- dataset adapters load raw data into a common internal format
- model adapters expose `fit`, `predict`, or `zero_shot_predict`
- evaluator code computes metrics and writes run-result JSON
- leaderboard code reads only run-result JSON plus metadata files

The first implementation should favor explicit skipped-run records over silent omissions, especially for ineligible IO modes, insufficient history, inaccessible datasets, or unsupported evaluation modes.
