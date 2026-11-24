# Recover a Frankfurt Airport Dagster partition

Retain the `DAGSTER_HOME` and `FRANKFURT_AIRPORT_STATE_DIR` used by the failed run.
The SQLite instance stores run history. The state directory holds verified
handoffs, DuckDB and feature/model files. Keep both outside Git.

## Identify the failed stage

Every failed asset emits a Dagster warning and writes a local JSON alert
under `$FRANKFURT_AIRPORT_STATE_DIR/alerts/<run-id>/<stage>.json`. The alert records
the job, UTC month, release ID, source commit, error type and recovery job.
The handoff gets one retry before it emits a failure alert. For full error
details, read the Dagster run log for the same run ID. If the state volume
is unwritable, the warning and `HOOK_ERRORED` event remain in the instance.

```bash
uv run --locked python orchestration.py inspect_run "$run_id"
```

Inspect the failed stage, upstream materializations and input hashes. A
successful recovery shows only the selected stage starting. Check the output
hash, counts or lineage recorded in its materialization before closing the
incident. The original alert remains available as run history.

## Recover only the affected month and stage

With the original environment set up, use the job below as
`uv run --locked python orchestration.py <job> <YYYY-MM>` after resolving
the cause. Feature and training commands also need `FRANKFURT_AIRPORT_SILVER_ROOT`.
Training needs the pinned baseline report and the existing M4 Docker image.

| Failed stage | Check before retrying | Recovery job and success check |
|---|---|---|
| `approved_gold` | Restore or obtain a complete approved release with `_SUCCESS`, matching manifest and payload checksums. | `verify_month`. Confirm the verified label counts and new handoff. |
| `local_handoff` | Restore state-directory write access and check for conflicting files. | `resume_local_handoff`. Confirm the existing verified Gold result was reused. |
| `local_analytics` | Restore DuckDB access. If database contents disagree with the ledger, preserve the database for investigation and use a verified backup or fresh local rehearsal state. | `resume_local_analytics`. Check row and label counts, zero duplicate keys, and zero added rows if replaying an already-ingested release. |
| `bigquery_reconciliation` | Check the existing phase 03 release and ledger, the query cap, and read permission. Route a missing upload or incorrect ledger to the phase 03 operator. | `reconcile_month_bigquery`. Confirm the same manifest, reconciled counts and zero added rows. This command sends a capped `SELECT`. |
| `monthly_features` | Restore the Silver directory and required month plus preceding UTC day. Check the manifest and Parquet hashes. | `resume_month_features`. Verify the feature dataset ID, manifest and payload checksum. |
| `container_training` | Restore the local Docker runtime, the pinned image and the checked feature and baseline inputs. The pilot training partition is `2024-11`. | `replay_model_month`. Check the model and both report hashes against the M4 release manifest. |

An altered verified input, conflicting checkpoint or bad cached checksum
requires investigation. Retain the original state for diagnosis. Reverify
approved inputs in fresh state when there is an intentional input or code
change, then rebuild any affected downstream asset.

## Operate the local release sensor

The sensor is stopped by default and only submits the local DuckDB job.
For a pilot, point `FRANKFURT_AIRPORT_RELEASES_DIR` at a directory containing only the
approved partitions you want to exercise. With the same environment used
for the foreground jobs, start the sensor and run the daemon from this directory:

```bash
uv run --locked dagster sensor start -f orchestration.py -a defs geometry_release_ready
uv run --locked dagster-daemon run -f orchestration.py -a defs
```

The manifest hash and release ID form the run key. Later ticks skip the
same release. If a sensor-triggered run fails, follow its stage alert and
resume explicitly. To finish a local pilot, stop the sensor and interrupt
the foreground daemon.

```bash
uv run --locked dagster sensor stop -f orchestration.py -a defs geometry_release_ready
```
