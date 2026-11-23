# M08 · Orchestration with Dagster

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status** Accepted. · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

The open-source Dagster daemon and webserver run in WSL2 through
`dagster dev` with a persistent, local `DAGSTER_HOME`. Each asset starts
the existing `charging-forecast` command in a child process. Dagster records
the CLI name, dataset and pinned-model lineage, and the output manifest or
report. Candidate runs also record the new MLflow run, version and database.

## Triggers

| Job | Trigger in Europe/Berlin | Command |
| --- | --- | --- |
| `daily_batch_scoring` | Every day at 06:00, for that day's issue | `score-batch` |
| `daily_forecast_monitor` | Every day at 04:30, for the issue two calendar days earlier | `monitor-window` |
| `train_candidate` | First day of each month at 05:15, or an eligible M07 decision | `run-pipeline` |

The monitor tick leaves the last target hour time to close and its label
time to arrive, including during summer time. Ticks outside the configured
dataset issue range show a skip reason. Within the range, missing score or
feature artifacts fail the run and surface through the failure sensor.

The sensor reads `state/decisions/monitor-*.json`, verifies the M07 policy
result against the report and matches the dataset and model manifest
hashes to the active configuration. Dagster uses the M07 decision ID as
its persistent run key. A report for a held decision or a superseded input
does not launch a candidate. A future-dated decision waits: live ticks
defer it until wall time passes its `as_of`, and a disposable replay pins
an explicit clock with the `replay_clock` setting. Training waits until
the configured dataset's final label is available at the effective
training time. Retrospective tests can use a historical schedule tick or
an explicit replay `as_of`.

Training expects a published dataset and complete features for that
release. Candidate identity includes the dataset, feature and pin manifest
hashes and source commit, so repeated triggers on the same inputs can
reuse M05 outputs. Training writes its SQLite registry, reports and model
release files under the configured state directory. Any promotion continues
through the separate M05 pin command.

## Run in WSL2

From `Mlops-engineering/reference-workload`, materialize the dataset,
features, pinned model and M07 calibration. Paths in the
[example settings](settings.example.yaml) are relative to `workdir`. The
`workdir` itself is relative to the settings file. The state directory
holds scores, their manifests, local MLflow artifacts and monitor results.

```bash
uv sync --locked
export CHARGING_FORECAST_ORCHESTRATION_CONFIG="$PWD/../08-orchestration-dagster/settings.example.yaml"
export DAGSTER_HOME="$PWD/data/m08/dagster"
mkdir -p "$DAGSTER_HOME"
test -e "$DAGSTER_HOME/dagster.yaml" || printf 'telemetry:\n  enabled: false\n' > "$DAGSTER_HOME/dagster.yaml"
uv run --locked dagster dev -m charging_forecast.orchestration --host 127.0.0.1 --port 3000
```

In the local Dagster UI, enable the three schedules and
`retraining_decision_sensor` and `orchestration_failure_sensor` when ready.
They start disabled on a fresh instance. Keep the same `DAGSTER_HOME` to
preserve run history and sensor deduplication. The daemon can only dispatch
while WSL2 is running. Compare score manifests to expected issue dates
after downtime and launch any missing days explicitly.

## Recover a failed day

Each CLI step has two retries with a two-second delay. After those retries,
the Dagster run shows failure and the failure sensor writes
`state/failures/<run-id>.json` with the job, affected issue or trigger,
timestamp and Dagster run path. Open that run to see the CLI error and its
attempts. Fix the underlying data or artifact problem before re-executing
with the same config. Keep the failure record alongside the successful run.

For a specific scoring date, launch `daily_batch_scoring` with the config
below. Use a date from the configured issue range.

```yaml
ops:
  batch_forecast:
    config:
      issue_date: "2026-12-30"
```

An unavailable forecast partition can block scoring before a monitor
report exists. In that case the Dagster scoring or monitor failure record
gives the affected issue date. A local failure journal supports inspection
after the process exits.

## Acceptance

1. Replay a scheduled scoring tick, evaluate its score with M07, and
   observe the local daemon launch a candidate with MLflow lineage.
2. Compare the direct and orchestrated score manifest and Parquet bytes.
3. Inject a fault in a disposable score run, observe retry exhaustion and
   the failure journal, then repair the same issue and verify its output.

Dagster run keys and triggers follow the
[official schedules and sensors API](https://dagster.io/docs/api/dagster/schedules-sensors).
M09 extracts the workload's pipeline and orchestration into a reusable
template.


## Session handoff

M08 is closed. The scheduled replay, live sensor-triggered training,
failure recovery, the final-candidate replay under an explicit clock
(A4) and the direct training reuse comparison (A5) all passed. See the
[acceptance record](evidence/m08-acceptance.md). The remaining open
decision for M09 is the second workload; see the
[delivery plan](../docs/delivery-plan.md).
