# Dagster Guide

This guide describes the supported Dagster orchestration paths in SoloLakehouse v2.5.

## Access Dagster UI

```bash
make up
make dagster-ui
```

Or open `http://localhost:3000`.

## Run Demo Data Flow

```bash
make demo
```

`make demo` executes `demo_data_flow_job` via `dagster-webserver`, then verifies Hive Gold and Iceberg Gold row counts through Trino. This is the v2.5 acceptance and recording path.

## Run Full Pipeline

```bash
make pipeline
```

`make pipeline` executes `full_pipeline_job`, which includes the demo data-flow assets plus `ml_experiment`.

## Asset Graph

Current dependency chain:

Demo path:

`ecb_bronze` and `dax_bronze` -> `ecb_silver` and `dax_silver` -> `gold_features`

Full pipeline adds:

`gold_features` -> `ml_experiment`

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
