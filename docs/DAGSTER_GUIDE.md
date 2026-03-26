# Dagster Guide

This guide explains how to run and operate the SoloLakehouse Dagster orchestration in v2.

## Access the Dagster UI

1. Start services:

```bash
make up
```

2. Open the UI:

```bash
make dagster-ui
```

Or open `http://localhost:3000` directly.

## Trigger a manual pipeline run

### From UI

1. Open `http://localhost:3000`.
2. Go to **Assets**.
3. Select the full asset graph (or specific assets).
4. Click **Materialize**.

### From CLI

```bash
make pipeline
```

`make pipeline` executes `full_pipeline_job` through the Dagster webserver container.

## View asset lineage

In the Dagster UI:

1. Open **Assets**.
2. Select any asset (for example `gold_features`).
3. Switch to the lineage graph view to inspect upstream/downstream dependencies.

Current dependency chain:

`ecb_bronze` and `dax_bronze` -> `ecb_silver` and `dax_silver` -> `gold_features` -> `ml_experiment`

## Enable or disable the daily schedule

The schedule is `daily_pipeline_schedule` (06:00 UTC weekdays).

In UI:

1. Open **Automation** (Schedules).
2. Find `daily_pipeline_schedule`.
3. Toggle to start/stop it.

## Re-run only failed parts

Use asset-level rematerialization:

1. In **Runs**, open a failed run.
2. Inspect failed assets.
3. Re-materialize only failed assets (and required downstream/upstream assets if needed).

This avoids rerunning the full pipeline when only one stage failed.

## `make pipeline` vs `make pipeline-legacy`

- `make pipeline`: Dagster-native execution (`full_pipeline_job`) and orchestration path for v2.
- `make pipeline-legacy`: legacy script path using `scripts/run-pipeline.py` (kept for migration fallback).
