# Cloud verification — G01 first cloud delivery

<!-- [李淳风·2026-11-20] Task 3.4 acceptance evidence (plan: docs/implementation.md,
Phase 3). Recorded live against project slh-gcp-test, region europe-west3. -->

## What was proven

The energy pipeline publishes a versioned sample window to Cloud Storage and
BigQuery from a container running on Cloud Run — on demand and on a schedule
— with every step driven by committed code: a GitHub Actions workflow builds
the image, plans and applies Terraform through Workload Identity Federation
(no key material anywhere), and the Cloud Run job writes immutable raw
objects, merges keyed rows and appends a release row.

## Delivery trail

| Step | Evidence |
|---|---|
| Implementation (publisher, container, IaC, workflow) | PR #173, merged; plan job green via WIF: `Plan: 22 to add, 0 to change, 0 to destroy` |
| Byte-stream fix (first live execution crash) | PR #174, merged; regression test mirrors the real client contract |
| Scheduler auth fix (OIDC → OAuth) | PR #175, merged |
| First apply | run 44796170071, apply green in 1m01s |
| Fix applies | runs 44807101466 and 44809613591, apply green |

## Bootstrap record (one-time, outside Terraform)

`infra/BOOTSTRAP.md` §2–§4, executed 2026-11-20 by the project owner: state
bucket `slh-gcp-test-tfstate`; deployer SA `github-deployer` with nine
project-level roles; WIF pool `github-pool` + OIDC provider `github-provider`
scoped to `attribute.repository=="Jiahong-Que-9527/SoloLakehouse"`;
`workloadIdentityUser` binding. Acceptance: an impersonated
`gcloud storage ls` listed the state bucket with no key material.

Live prerequisites discovered during delivery (each broke a first run; now in
BOOTSTRAP.md §2): every `main.tf` service plus `cloudresourcemanager`
pre-enabled (Terraform cannot manage services without CRM); the Artifact
Registry repo `energy` created and imported into state (build-push needs it
before the first apply can ever create it); an App Engine app in
europe-west3 (Cloud Scheduler prerequisite).

## Executions and acceptance

Window 2026-06-08 → 2026-06-15 (Europe/Berlin), packaged sample,
`input_checksum`
`1465e3e4d7f5a529d0282bf9aea2a5621b1c7b1a7dc61f9ee42952eb1f4a7b25` —
identical across all four release rows.

| # | Execution | Trigger | Result | Ledger row |
|---|---|---|---|---|
| 1 | `energy-pipeline-mtj5r` | manual (pre-fix image) | failed: BQ load rejected raw bytes → PR #174 | `aa25ae78…` passed 672 |
| 2 | `energy-pipeline-m6mhg` | manual (post-fix, Task 3.1) | succeeded 16.26s; 672 rows, keys unique | `c1402545…` passed 672 |
| 3 | `energy-pipeline-74qj8` | manual repeat (Task 3.2) | succeeded; rows unchanged | `0bede9e6…` passed 672 |
| 4 | `energy-pipeline-jlj6z` | scheduler, forced (Task 3.3) | succeeded; rows unchanged | `0f249cdb…` passed 672 |

- **Raw layer:** 8 objects = 4 immutable CSV + manifest pairs under
  `raw/sample/de_load/dt=2026-06-08/`; no overwrites.
- **Idempotency (Task 3.2):** row count 672 → 672, distinct business keys
  672 → 672, per-group counts unchanged (`DE` / `actual_load_mwh`). The
  `DATE(interval_start)` reference query holds 8 UTC day-groups (96 rows per
  full day, 8 and 88 on the boundary days) identically before and after the
  repeat run.
- **Scheduling (Task 3.3):** `energy-weekly` ENABLED, `15 5 * * 1`,
  Europe/Berlin; next scheduled fire 2026-11-23T04:15:00Z (= 05:15 Berlin);
  `lastAttemptTime` 2026-11-20T20:18:31Z is the forced run recorded above.
- **Failure handling observed:** `insert_release` intentionally precedes the
  merge, so the ledger records every attempt; an infrastructure failure after
  a passed validation is visible in row 1 (ledger says passed/672, the merge
  never happened, Cloud Run shows the failed execution) and a data-quality
  failure would write `quality_status=failed` and leave the table unchanged.
  The failed raw pair from execution 1 remains in the bucket by design —
  raw objects are never overwritten or deleted.

## Identities used

- Local operator: project owner `jiahongque25@gmail.com` (OAuth, user mode).
- CI plan/apply and image push: `github-deployer@slh-gcp-test.iam
  .gserviceaccount.com` via Workload Identity Federation, repo-scoped.
- Runtime: `energy-job@slh-gcp-test.iam.gserviceaccount.com` — objectCreator
  and objectViewer on the raw bucket, dataEditor on the `energy` dataset,
  jobUser and run.developer on the project.
- Scheduler → job: OAuth access token for `energy-job`, minted by Cloud
  Scheduler.

## Cost

Billing account `01FCE3-C90698-BFE584` for the acceptance day
(2026-11-20): **Total €0.00** — usage was fully offset by free-tier
discounts and trial credits, and the Free Trial banner shows €0 of
€269 used. The per-service breakdown for `slh-gcp-test` is pending
the billing-data lag; expected drivers are Artifact Registry image
storage (~570 MB), negligible BigQuery storage for 672 rows, and four
Cloud Run executions billed by CPU-time only. Charges visible in the
report from sibling projects on the same billing account (e.g. Vertex
AI usage from `sololakehouse`) are not G01 charges — this repo's GCP
cost gate ([AGENTS.md](../../AGENTS.md)) exists to keep it that way.

## Out of scope (unchanged, design §2)

G02 API, event corrections (G03), release catalog and IAM product model
(G04), training (G05), the reusable project factory (G06), live SMARD
downloads from cloud IPs, growing backfills and a historical-refresh policy.

## Scheduled-run verification (pending, first fire 2026-11-23)

Baseline recorded 2026-11-22 (read-only checks, post-acceptance): four
`energy-pipeline` executions and four `energy.load_release` rows, all
`passed`, all with `git_sha` null — expected before the GIT_SHA fix —
with the latest row `0f249cdb2d1c44ab8155fb810b178302` published
2026-11-20T20:18:44Z by the forced run (`energy-pipeline-jlj6z`,
`energy-job` identity). Row 1 (`aa25ae78…`, `energy-pipeline-mtj5r`)
remains the recorded infrastructure-failure case: ledger says passed,
the merge never happened.

Since then the deployed image is `energy-pipeline:7322e658` and the
job's `GIT_SHA` env carries `7322e658…` ([PR
#251](https://github.com/Jiahong-Que-9527/SoloLakehouse/pull/251)), so
the next manifest is expected to be the first with a real `git_sha`.

Checklist for the Monday 2026-11-23 05:15 Europe/Berlin fire
(`15 5 * * 1`, Europe/Berlin):

1. A new execution of the `energy-pipeline` job run by
   `energy-job@slh-gcp-test.iam.gserviceaccount.com` (scheduled, not a
   manual run-by) — record the execution id.
2. `energy.load_release` gains a fifth row with a new `release_id`.
3. The new manifest records `git_sha = 7322e658…` (live confirmation of
   the GIT_SHA fix) and `quality_status = passed`.
4. The run stays inside the free tier (single task, well under a minute,
   fixed sample window) — record the observed cost line items.
5. Update this section from "pending" to the recorded result and adjust
   the [GCP roadmap](../../gcp/README.md) check item.

Verification commands (read-only, no cost-gate approval needed):
`gcloud run jobs executions list --job energy-pipeline --region
europe-west3 --project slh-gcp-test`, `bq query --use_legacy_sql=false
'SELECT * FROM energy.load_release ORDER BY published_at'`, and the
newest `*.manifest.json` in the raw bucket.
