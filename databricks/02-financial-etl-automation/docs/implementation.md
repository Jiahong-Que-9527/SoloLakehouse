# Financial ETL Automation implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** Accepted on Databricks Free Edition (2026-11-24). [Brief](../README.md) · [Design](design.md)

## First delivery

Turn a pinned D01 transformation into a scheduled, repairable workspace job. Start with a dedicated test target, a valid window, a faulty batch and the expected release for the valid input.

## Implementation sequence

1. Define the job parameters, target schema and release identity. Trace one window through ingest, transform, quality and publish. Decide how a repeat request finds an already published result.

2. Validate the dependency graph and bundle target before deployment. Run fixture tests on a PR; deploy the validated revision to the test target and record the workspace job ID, commit and runtime identity.

3. Run a known-good scheduled window. Capture task states, output counts, Delta versions and the release pointer. Use this as the comparison for the failure exercises.

4. Interrupt a transient task, then submit a duplicate-key or invalid batch that should fail quality. Verify retry behavior for the former and skipped publication for the latter. Query the previous release after failure.

5. Repair the batch, rerun the affected window and repeat that request once. Check business-key uniqueness and one accepted release for the corrected inputs. Record the backfill bounds, durations and any remaining compute or schedule.

## Portfolio evidence

Evidence: link a successful schedule, a failed quality task and a repaired release. Explain why a transient retry is safe and why retrying invalid input alone cannot repair it. Link measured results from the brief after execution.

## Free Edition verification

The CLI deployed the job to `workspace.ecb_d02_dev_20261124_194938` using
revision `1f45f7911df6af272b81152ef10344ee59e0f841`. The schema and bundle
state were isolated from D01. The scheduler was restored to `PAUSED` as
soon as the acceptance tick created a run.

| Scenario | Observed outcome | Run |
|---|---|---|
| Scheduled seed | The platform triggered the job. All four tasks succeeded and the initial Gold release has 10 rows. | [641014598139084](https://dbc-7395c3c6-fdc9.cloud.databricks.com/jobs/482115501940431/runs/641014598139084?o=7474653372862099) |
| Faulty correction | A conflicting FX key failed quality. Publish was skipped with `UPSTREAM_FAILED`. | [953398818471373](https://dbc-7395c3c6-fdc9.cloud.databricks.com/jobs/482115501940431/runs/953398818471373?o=7474653372862099) |
| Corrected backfill | Ingest failed once after the Bronze commit and then succeeded without repeating the write. Exactly one further Gold release was written. The Silver fingerprint outside 2025-02-05 stayed identical. | [437122716618586](https://dbc-7395c3c6-fdc9.cloud.databricks.com/jobs/482115501940431/runs/437122716618586?o=7474653372862099) |
| Replay | An initial replay timed out in ingest. The subsequent run succeeded, reused the corrected release and left the ledger at two entries. | [509417873317060](https://dbc-7395c3c6-fdc9.cloud.databricks.com/jobs/482115501940431/runs/509417873317060?o=7474653372862099) |

The original Serverless defaults added an extra quality attempt to the first
faulty correction. With auto-optimization disabled, the
[permanent-error rerun](https://dbc-7395c3c6-fdc9.cloud.databricks.com/jobs/482115501940431/runs/735224049897185?o=7474653372862099)
made exactly one quality attempt and again skipped publication. A separate
read-only run, `1074522381717023`, checked the ledger and both Gold Delta
tables directly. Silver had 10 rows and 10 distinct business keys. Each Gold
table had 10 rows and one Delta version. The original release remained
visible during the first failure, and the post-fix failure left the corrected
release current. The [structured evidence](../evidence/free-edition-acceptance.json)
records task IDs, attempts, timings, window boundaries, source batch and
Git revision.

### GitHub Actions deployment

The manual [GitHub Actions run](https://github.com/Jiahong-Que-9527/SoloLakehouse/actions/runs/45484497624) passed both
test and deploy from `main` at `18df3c35ab13bd92d0659274d8cb12616fe37871`. It created
job `919065967479203` for `workspace.ecb_d02_dev_ci_20261124_204744`.
Databricks confirmed all four task dependencies and retry settings.
The [manual smoke run](https://dbc-7395c3c6-fdc9.cloud.databricks.com/?o=7474653372862099#job/919065967479203/run/96282487473973) then ran all four tasks
successfully and published `d02-d48114bd9734a2fa5a45cf2b` with 10 Gold rows.
The job schedule stayed `PAUSED` through both deployment and the smoke run.
