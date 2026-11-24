# Design: Financial ETL Automation

**D02 · Implemented.** The bundle runs four tasks against a dedicated schema.

Run the D01 transforms as a job with explicit task order, a failed-task stop, and a deployment that comes from Git. The project proves that a person does not have to start the notebook for a release to exist.

The job uses D01's fixtures and transforms from the deployed Git revision.
It stages immutable Bronze batches by input hash and merges Silver on
`(series_key, observation_date)`. The task event table records each result
with job run ID, window, batch, Git revision and elapsed time.
Publication writes a versioned Gold table and then inserts the release row.
The current release view selects the latest successful release row, so a
failed write before ledger insertion leaves the prior release visible.
A repeated publisher returns the existing release ID without creating
another row or changing which release is current.

The project [brief](../README.md) fixes the tasks.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Job | One Lakeflow Job with four tasks: `ingest`, `transform`, `quality`, `publish`. |
| Order | Each task depends on the previous one. `publish` does not start unless `quality` succeeds. |
| Quality failure | `publish` is skipped. The existing Gold version stays the current release. |
| Deploy | Declarative Automation Bundles, using the current CLI and bundle format. Old `dbx` examples are not a source. |
| Targets | `dev` and `prod` in the same bundle, different schemas. GitHub Actions dispatch selects `dev` or `prod` explicitly. Each target requires its own schema prefix. |
| CI | GitHub Actions runs local tests. A manual deployment validates the authenticated target after tests pass. |
| Backfill | Job parameters `window_start` and `window_end`. The tasks pass them through. A backfill uses the same MERGE rules as D01. |
| Rerun | A retry or a manual rerun of a succeeded window does not add Silver keys. |
| Evidence | Each run records run id, task states, window, `source_batch_id`, git sha, and duration. |
| Notification | The job has a failure destination. v1 evidence is the run record. A paging tool is not required. |

## 2. Boundary

In scope: splitting the D01 logic into tasks, the bundle, the workflow, retry settings, and the run record.

Out of scope: changing the Silver grain, CDC, Unity Catalog role design, and model training. The tasks call the same transform functions D01 tests.

## 3. Architecture

```text
GitHub Actions
  tests + bundle validate
          |
          v
Bundle deploy to target dev or prod
          |
          v
Lakeflow Job
  ingest -> transform -> quality -> publish
          |
          v
Run record in the target schema
```

`ingest` writes Bronze for the window. `transform` merges Silver. `quality` checks key uniqueness, reject count, and the expected sample rows when the window is the known fixture. `publish` writes the Gold release row and points the current release at that version.

## 4. Task contract

Shared parameters: `window_start`, `window_end`, `git_sha`, `source_batch_id`.

| Task | Success | Failure |
|------|---------|---------|
| `ingest` | Bronze batch written for the window | No Silver change |
| `transform` | MERGE finished, reject count attached | No publish |
| `quality` | Uniqueness holds and rejects are within the contract | Publish skipped, Gold version unchanged |
| `publish` | New `release_id` points at this Silver version | Run marked failed, previous release id unchanged |

Retries: `ingest` and `transform` retry twice on a task error. `quality` does not retry a failed check. A failed check is a data result, not an infrastructure error. `publish` retries once and remains idempotent on `source_batch_id`.

Timeouts are set per task. A stuck task fails the run rather than holding a warehouse open.

## 5. Behaviour

- A failure message names the task key. The downstream tasks are `UPSTREAM_FAILED` or skipped, and the run record says which.
- Repairing the input and rerunning with the same window produces one current release. An earlier failed run remains in the run history.
- `dev` and `prod` do not share a schema. A dev run cannot write the prod release table.
- Bundle files in git are the only supported way to change the job. A change made in the workspace UI is drift and is overwritten on the next deploy.

## 6. Delivery and cost

The scheduled run, when enabled, uses the sample window and Serverless compute. The schedule starts paused. For acceptance, enable a single scheduled tick and restore the paused setting once the run is queued.

Free Edition limits on concurrent tasks are respected: four tasks in one job, one job at a time. If the workspace rejects a bundle feature, the evidence records the feature and the substitute. It does not claim the rejected feature ran.

## 7. Acceptance

1. Deploy from GitHub Actions. Record one run in which all four tasks succeed, with the run id and the release id.
2. Feed a fixture that fails `quality`. Show that `publish` did not run and that the previous Gold version is unchanged.
3. Repair that fixture and rerun. Show one new release, the failed run still visible, and the run record linked to `source_batch_id` and git sha.
4. Start a backfill for a stated date range and show that dates outside the range were not rewritten.

## 8. Handoff

D06 may copy this bundle layout into a template after this job has deployed once. D04 can grant read access to the published schema. This job's deploy identity is not reused as a reader's identity.

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
