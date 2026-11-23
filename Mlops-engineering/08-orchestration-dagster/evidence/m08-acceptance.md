# M08 · Acceptance evidence

WSL2, 2026-11-23 UTC, checkout
`c1760303b601ae5d71c35c581303a765752564be` plus the M07 and M08 worktree
changes. Python 3.13.14, uv 0.13.9, Dagster 1.13.31 and MLflow 3.18.0.
Dagster used a disposable persistent instance and a loopback-only
webserver, with telemetry disabled.

Inputs were the M07 tariff replay dataset `dataset-m07-tariff-drill`
(published locally with 27 validation checks) and
`feat-v1-dataset-m07-tariff-drill` (729 issue days). Their manifest
SHA-256 digests were
`2fdd716aeb54b4267c1a8bb801f5be0ac76a3e38b9cf5e4a7b0e9d48f43889ad`
and `3af2e3052fef7b3ea73db1494c218021e5018f73bad8ea780b951411e8e08d40`.
The pin was `model-v001`, registry version 1, source MLflow run
`f5c328812abd40b7993eb5cf91b266ad`, pin manifest SHA-256
`c31adfd530a70d2e0e1edcb41b5183064be0b9c1e83f237900a970aaec569f86`.

## A1 · Schedule replay and live sensor run

Evaluated `batch_scoring_schedule` with a
`build_schedule_context(scheduled_execution_time=...)` tick at
2026-12-30 06:00 Europe/Berlin. Executed its returned run config on the
persistent Dagster instance to replay that historical slot. Run
`13b73d43-1f96-4e51-8610-733899b2bcf9` materialized `batch_forecast`
with `score-batch`, 960 rows and the input and output lineage above.

Likewise evaluated `forecast_monitor_schedule` at 2027-01-01 04:30
Europe/Berlin. Run `9bb69891-f571-4f34-af34-a22042e7cfc2` evaluated the
same scoring issue with `monitor-window`. Its replay `as_of` was
03:30 UTC, after the latest dataset label arrived at 01:00 UTC.
The decision was `retrain` with 14 drift breaches and ID
`fa5405dd5c98717d2926e70cd8e36b425300a2048f01f165a8965667fc10b666`.

With the two local sensors enabled, the actual daemon picked up that
record at 00:22:13 UTC and launched `train_candidate` run
`ba4f99f4-58de-4f6c-adcd-60843c64a305`. The run succeeded at 00:28:12
UTC. Its `run-pipeline` call reused features, trained and evaluated on
the 23-fold protocol, registered local MLflow run
`f5d9fefda5ba4a20a3b2e5f4bc5011b2` as version 1, and published
`model-m08-c834a929bf351337`. Model MAE was 7.246101 kWh against
seasonal-naive 9.099315 and station-median 11.800357 on this shifted
dataset. The candidate stayed in the local candidate registry and the
serving pin remained `model-v001`. Later sensor ticks skipped the same
decision ID.

## A2 · Direct and Dagster output parity

Ran `score-batch` directly with the same dataset, feature release, pin
and issue date, with separate score and score-manifest output directories.
The direct and Dagster score manifest and Parquet were byte-identical.
The score manifest SHA-256 was
`b1f17b4f069c038d9b16c0b66f485afad0361d8d70d159dffdfa766db2fc628a`;
the prediction Parquet SHA-256 was
`e51830dd824784a55b611d3334dbe8bea7874b0f797b5a39e0d90fa44ae55946`.

## A3 · Retry exhaustion and recovery

Two faults were exercised in disposable state:

- Removed the December feature partition while replaying the scheduled
  2026-12-29 scoring tick. Run `04d95a95-3ccb-4302-91d3-428c9257be03`
  recorded two retries and a failure, with no score manifest for the
  issue. Restored the partition and replayed the same run config.
  Run `f8d1c219-8e47-46f4-badd-810453366655` succeeded.
- Inserted a conflicting score manifest for 2026-12-28 and launched
  `daily_batch_scoring` through the running Dagster instance. Run
  `d2a60ee2-8f20-4c55-99c7-298d1372ac01` failed after its third attempt
  at 00:24:09 UTC. At 00:24:22 UTC the live failure sensor journaled
  the affected date and Dagster run path. Moved the injected manifest
  aside and launched the same issue again. Run
  `86d63ded-790b-418c-8e0e-67b1598504a0` succeeded at 00:25:52 UTC
  and wrote the score manifest.

The recovery steps use the [local run guide](../README.md#recover-a-failed-day).

## Checks and session stop

The full workload regression passed 72 tests in 271.55 seconds with
`uv run --locked --offline --no-sync pytest`. Dagster definitions
loaded, schedule tests covered tick dates and monthly eligibility, and
sensor tests covered duplicate, stale, invalid and hold decisions.
Ruff lint and format checks passed. The lockfile SHA-256 was
`9cf9614f9834a9a08d34cc61756fd60350dacff974b32a6c22850a5d692f63d2`.
The six focused M07 and M08 tests passed again at closeout.

The completed candidate manifest SHA-256 was
`6d65455bbdc3f18be7d299e07dc6cabb7000ddfd3e667effab381110fea3bad3`.
A second live run, `227ac17a-81a8-4e63-adc2-e2716d7ed4f6`, picked up
the 2026-12-28 decision to check the final candidate identity and the
isolated artifact directory. The Dagster test deployment was shut down
at 00:30:51 UTC, interrupting that run during training. The final replay
and a direct training reuse comparison remain to be verified.

## A4 · Final replay with an explicit clock (2026-11-23)

The interrupted final replay was completed on a fresh disposable
instance (new `DAGSTER_HOME`, loopback-only webserver, telemetry
disabled) against the unchanged M07 drill inputs —
`dataset-m07-tariff-drill` (manifest `2fdd716a…89ad`, `_SUCCESS`
marker restored after the drill had left the release without it),
`feat-v1-dataset-m07-tariff-drill` (`3af2e305…8d40`) and pin
`model-v001` (`c31adfd5…9f86`).

The sensor gained an explicit clock for exactly this case: live ticks
defer future-dated decisions until wall time passes their `as_of`, and
a disposable replay pins a `replay_clock` in settings. The replay
settings pointed at the drill dataset and pinned
`replay_clock: 2027-01-01T03:30:00+00:00`, because the drill dataset's
labels extend to 2026-12-30 and the readiness guard must refuse a
wall-clock tick of 2026-11-23 — the same no-lookahead rule A1 ran
under. Live deferral and replay pickup are unit-tested
(`test_sensor_defers_future_decisions_until_the_clock_passes`).

The daemon picked up the M07 retrain decision `600ac4f9…211a`
(12 drift breaches, issue 2026-11-15) and launched `train_candidate`
run `9b4f83f9-9f34-4f93-bfa1-4b369d946b66`. It ran 12:37:09–12:47:33
UTC and succeeded. Candidate `model-m08-2f806d894e44e365` reproduced
the A1 metrics bit for bit (MAE 7.246101 vs seasonal-naive 9.099315
and station-median 11.800357, 23 folds) with the final code at commit
`cbd89178…7d63`, its own isolated `candidate-models`,
`candidate-releases`, `candidate-reports` and `mlflow.db` under the
state directory, and the serving pin untouched at `model-v001`. The
run key reused the M07 decision ID, so later sensor ticks skipped the
same decision.

## A5 · Direct reuse against the orchestrated artifacts

`run-pipeline` was then executed directly with the same arguments the
asset used (same config, release, features, candidate ID, output,
models, releases and tracking directories). It reported
`features reused, train reused (MAE 7.246101), register reused v1,
publish confirmed` without launching a new MLflow run (10 runs in the
tracking database before and after). The manifest, report and artifact
bytes were identical before and after:

- manifest `3b44d72d…60c`, report JSON `b07751ef…fa2`,
  report Markdown `5b53c6df…14d8`, artifact `9dabfc78…87f6` — the
  artifact checksum matches the manifest's recorded `artifact.sha256`.

With A1–A3 above, all M08 acceptance checks are complete.
