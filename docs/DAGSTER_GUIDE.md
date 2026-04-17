# Dagster Guide

This guide describes the **only supported runtime orchestration path** in SoloLakehouse v2.5.

## Access Dagster UI

```bash
make up
make dagster-ui
```

Or open `http://localhost:3000`.

## Run Pipeline

```bash
make pipeline
```

`make pipeline` executes `full_pipeline_job` via `dagster-webserver`.

## Asset Graph

Current dependency chain:

`ecb_bronze` and `dax_bronze` -> `ecb_silver` and `dax_silver` -> `gold_features` -> `ml_experiment`

In UI:
1. Open **Assets**
2. Select an asset
3. View upstream/downstream lineage

## Schedule and Sensor

- Schedule: `daily_pipeline_schedule` (06:00 UTC weekdays)
- Sensor: `ecb_data_freshness_sensor`

In UI:
1. Open **Automation**
2. Toggle schedules/sensors

## Re-run Strategy

When a run fails:
1. Open the failed run in **Runs**
2. Identify failed assets
3. Re-materialize only failed assets (and required dependencies)

This keeps recovery scope small and avoids full pipeline reruns.
