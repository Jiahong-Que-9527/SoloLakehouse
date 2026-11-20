# Implementation plan: G01 first cloud delivery

<!-- [李淳风·2026-11-20] Phased plan for the first Cloud Run Job + Cloud Storage + BigQuery delivery. -->
<!-- [李淳风·2026-11-20] Region decision (owner, 2026-11-20): europe-west3 for every regional resource. -->
<!-- Status: planned. No implementation code written yet. -->

**Goal:** Deliver one verified SMARD week from a Cloud Run Job through Cloud Storage into
BigQuery, deployed by GitHub Actions with Terraform and Workload Identity Federation, and
record the acceptance evidence required by the design.

**Spec:** [Design](design.md) fixes the architecture, contracts and acceptance criteria.
The [project README](../README.md) § "Cloud acceptance (planned)" states the three
acceptance gates. This plan sequences the work, records the decisions an implementer
cannot invent, and marks every step only the project owner can perform with **[USER]**.

## How to read this plan

- Phases 0–3 are sequential. Tasks 1.1–1.4 are independent except where an Interfaces
  block states otherwise.
- **[USER]** = manual gate: needs the owner's hands, credentials or explicit approval.
  Everything else is agent-executable in WSL without cloud access.
- Each code task ends with the project checks green:
  `uv run --locked pytest` and `uv run --locked ruff check . && uv run --locked ruff format --check .`

## Decisions fixed by this plan

| Topic | Decision |
|---|---|
| Region | `europe-west3` (Frankfurt) for every regional resource: bucket, dataset, tables, job, scheduler, Artifact Registry. Owner is Frankfurt-based; SMARD is German public data; co-location avoids cross-region load/query paths. |
| BigQuery location | Dataset location `EUROPE-WEST3`, not the `EU` multi-region. |
| Cloud data mode | v1 job reads the bundled deterministic synthetic sample week only (`--data-mode sample`, rows carry `source=sample`). Downloading SMARD from cloud IPs is out of scope: the downloader's pacing/robots policy is engineered for one local downloader (README § "Bounded automatic downloads"). |
| Sample dataset | One synthetic normal week (672 rows, 2026-06-08 → 2026-06-15) and one synthetic autumn DST day (100 rows), generated with the existing test fixture generator, committed at `src/energy_pipeline/data/sample_week.csv` and `src/energy_pipeline/data/sample_autumn_day.csv`. Synthetic data may live in Git; real exports may not. |
| New CLI command | `energy-pipeline publish-cloud` (signature in Task 1.1). |
| Cloud dependencies | New optional extra `cloud` in `pyproject.toml`: `google-cloud-storage>=3`, `google-cloud-bigquery>=3`. Core installs and existing CI stay unchanged. |
| Release identity | `release_id = uuid4().hex` per publish attempt; Cloud Run execution id read from the `CLOUD_RUN_EXECUTION` environment variable (empty when run locally). |
| Publish mechanics | Load the window into a per-release staging table, then `MERGE` into `energy.metric_observation` on `(area, metric, interval_start)` inside one BigQuery job; drop the staging table afterwards. A failure path never touches `metric_observation`. |
| Job retries | Cloud Run Job `max-retries 0`, task count 1. A failed validation is data, not infrastructure: reruns are manual, so no duplicate release rows. |
| WIF bootstrap | Pool, provider and deploy SA are documented one-time gcloud commands in `infra/BOOTSTRAP.md`, run with the owner's identity. Deliberately outside `main.tf`: the identity that applies `main.tf` cannot be created by `main.tf`. Terraform state lives in a GCS bucket created by the same bootstrap. |

## Global constraints

- `europe-west3` is the only region used anywhere.
- No service-account keys, no credentials, no raw datasets and no Terraform state in Git.
- SMARD attribution and licence links travel in every manifest and release row
  ([data use](data-use.md)).
- A validation failure writes `quality_status=failed` to `energy.load_release` and must
  not change `energy.metric_observation` (design §5.4).
- Raw objects are immutable: each run writes
  `raw/<source>/de_load/dt=YYYY-MM-DD/<run_id>.csv` + `.manifest.json`; committed objects
  are never overwritten. Sample rows land under `raw/sample/`, never `raw/smard/`.
- CI runs without cloud access: all cloud behaviour is exercised through in-memory fakes.

## Review focus

1. **Failed publish must not mutate the table** — duplicate-key, missing-interval and
   null-value fixtures produce a failed release row and an unchanged
   `metric_observation` (Task 1.1 step 3).
2. **Idempotent republish** — same window + same input checksum twice: identical business
   keys, row count 672, two release rows (Task 1.1 step 4; re-proved live in Task 3.2).
3. **DST boundary through the full cloud path** — the autumn sample (100 intervals)
   validates and publishes with correct UTC durations (Task 1.1 step 5).
4. **Contract boundary** — local `normalize` output keeps its current seven columns;
   only the cloud publisher adds `release_id` and `ingested_at` (Task 1.1 step 6).
5. **Raw prefix isolation and immutability** — sample rows under `raw/sample/`; a second
   run adds objects, never overwrites (Task 1.1 step 7).

---

## Phase 0 — Manual prerequisites

### Task 0.1 GCP project and billing **[USER]**

1. Create or select a test project in the Google Cloud console.
2. Link a billing account to the project.
3. Create a budget alert for the project (recommended threshold €10/month; the owner
   picks the number).
4. Record the project id; it becomes the value of every `project_id` below.

Verify: `gcloud projects describe <project-id>` returns the project.

### Task 0.2 Local tooling **[USER approves; install may be delegated]**

1. Install the Google Cloud CLI and Terraform (≥ 1.9) in WSL Ubuntu.
2. `gcloud auth login` and `gcloud config set project <project-id>`.
3. `gcloud auth application-default login` (for bootstrap commands in Phase 2).
4. Confirm GitHub admin access to `Jiahong-Que-9527/SoloLakehouse`.

Verify: `gcloud projects describe <project-id>` and `terraform version` succeed in WSL.

## Phase 1 — Local code and IaC (agent, no cloud access)

### Task 1.1 Cloud publisher module

**Files:**
- Create: `src/energy_pipeline/cloud_publish.py`
- Create: `src/energy_pipeline/data/sample_week.csv`, `src/energy_pipeline/data/sample_autumn_day.csv`
- Modify: `src/energy_pipeline/cli.py` (register the `publish-cloud` subcommand)
- Modify: `pyproject.toml` (add the `cloud` optional extra)
- Test: `tests/test_cloud_publish.py`, `tests/test_cli_cloud.py`

**Interfaces:**
- Consumes: `normalize.normalize(raw: bytes, window: Window) -> pa.Table` and
  `normalize.Window` from the existing package; parsing logic is reused, never duplicated.
- Produces (signatures later tasks and the Dockerfile rely on):

```python
# cloud_publish.py
@dataclass(frozen=True)
class PublishResult:
    run_id: str
    release_id: str
    row_count: int
    input_sha256: str
    quality_status: str  # "passed" | "failed"

class RawStore:
    def put(self, bucket: str, prefix: str, run_id: str,
            csv_bytes: bytes, manifest: dict) -> None: ...

class Warehouse:
    def merge_observations(self, project: str, dataset: str, table: str,
                           rows: pa.Table, release_id: str,
                           ingested_at: datetime) -> int: ...
    def insert_release(self, project: str, dataset: str, record: dict) -> None: ...

def publish_window(store: RawStore, warehouse: Warehouse, *, csv_bytes: bytes,
                   window: Window, bucket: str, project: str, dataset: str,
                   mode: str) -> PublishResult: ...
```

- CLI surface: `energy-pipeline publish-cloud --mode sample --bucket BUCKET
  --project PROJECT --dataset energy [--output-dir DIR]`. `--mode` accepts `sample`
  only in v1; the sample files ship inside the package.

**Steps:**

1. Write the failing tests:
   - `test_publish_sample_week_passes`: fake store/warehouse, 672 rows published, one
     release row `quality_status=passed`, raw objects under `raw/sample/de_load/dt=.../`.
   - `test_publish_adds_release_columns`: merged rows carry `release_id` and
     `ingested_at`; the local Parquet contract (seven columns) is unchanged.
   - `test_duplicate_key_fails_without_table_change`: corrupted fixture → release row
     `quality_status=failed`, zero rows merged, exit code 1.
   - `test_missing_interval_fails_without_table_change` and
     `test_null_value_fails_without_table_change`.
   - `test_autumn_dst_sample_publishes_100_rows`.
   - `test_repeat_run_new_object_same_keys`: second run adds a raw object, keeps the
     business keys and row count, adds a second release row.
   - `test_no_overwrite_of_committed_objects`.
2. Run `uv run --locked pytest tests/test_cloud_publish.py` — expect failures
   (module does not exist).
3. Implement `cloud_publish.py` against the signatures above; wire the `publish-cloud`
   subcommand into `cli.py` following the existing subcommand pattern; add the `cloud`
   extra to `pyproject.toml`; generate and commit the two sample CSVs with the existing
   fixture generator.
4. Run the full checks — expect green. Commit: `feat: add cloud publisher with sample mode`.

### Task 1.2 Docker image

**Files:**
- Create: `Dockerfile` (project root of `01-european-energy-pipeline`), `.dockerignore`

**Interfaces:**
- Consumes: the package with the `cloud` extra; the entrypoint runs
  `energy-pipeline publish-cloud --mode sample --bucket/--project/--dataset` supplied as
  job arguments by Terraform (Task 1.3).

**Steps:**

1. Write the Dockerfile: `python:3.12-slim` base, uv from a pinned
   `ghcr.io/astral-sh/uv` image, `uv sync --locked --extra cloud`, copy `src/` and
   package data, entrypoint on `energy-pipeline`.
2. Verify: `docker build -t energy-pipeline:dev .` succeeds;
   `docker run --rm --entrypoint energy-pipeline energy-pipeline:dev publish-cloud --help`
   prints the new command's help.
3. Commit: `feat: containerise the energy publisher`.

### Task 1.3 Terraform

**Files:**
- Create: `infra/versions.tf`, `infra/variables.tf`, `infra/main.tf`, `infra/outputs.tf`
- Create: `infra/BOOTSTRAP.md` (one-time commands for Task 2.2, including the state
  bucket creation and `terraform init -backend-config="bucket=..."` usage)

**Interfaces:**
- Consumes: the image name/tag as variable `image` (set by the workflow in Task 1.4);
  `project_id` variable; bucket name convention `<project_id>-energy-raw`.
- Produces: `job_name = "energy-pipeline"` output used by Task 3.1 commands.

**Resources (all `europe-west3` unless noted):**

1. `google_project_service`: run, storage, bigquery, artifactregistry, cloudscheduler,
   iamcredentials, sts, iam, serviceusage.
2. `google_storage_bucket` `<project_id>-energy-raw`: uniform bucket-level access,
   public access prevention, no versioning (objects are immutable by convention,
   writes are new objects).
3. `google_bigquery_dataset` `energy` (location `EUROPE-WEST3`).
4. `google_bigquery_table` `metric_observation` and `load_release` with the design §4
   schemas (`load_release`: release_id, window_start, window_end, input_checksum,
   row_count, git_sha, execution_id, quality_status, published_at).
5. `google_artifact_registry_repository` `energy` (format DOCKER).
6. Service account `energy-job` + least-privilege bindings per design §6: object
   creator/viewer on the bucket, `bigquery.dataEditor` on the `energy` dataset,
   `bigquery.jobUser` on the project, and permission to run the job for the scheduler
   identity (`roles/run.developer`, project-scoped in this single-purpose test project).
7. `google_cloud_run_v2_job` `energy-pipeline`: image var, service account `energy-job`,
   task count 1, max retries 0, args fixed to sample mode and the sample window.
8. `google_cloud_scheduler_job` `energy-weekly`: cron `15 5 * * 1`, timezone
   `Europe/Berlin`, HTTP target `POST .../jobs/energy-pipeline:run`, OIDC with the
   `energy-job` SA.
9. Service account `github-deployer` + Workload Identity Federation pool `github-pool`
   and provider `github-provider` (attribute condition restricting to
   `Jiahong-Que-9527/SoloLakehouse`), with `workloadIdentityUser` binding.

**Steps:**

1. Write the four `.tf` files; `infra/BOOTSTRAP.md` documents the WIF/state-bucket
   commands (used only in Phase 2, not applied by `main.tf`).
2. Verify: `terraform fmt -check`, `terraform validate` (no project needed yet).
3. Commit: `feat: terraform for the energy cloud delivery`.

### Task 1.4 Deploy workflow

**Files:**
- Create: `.github/workflows/energy-cloud.yml`
- Modify: none — the existing `energy-pipeline.yml` stays as-is.

**Interfaces:**
- Consumes: repo variables `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
  `GCP_STATE_BUCKET` (set in Task 2.3); WIF auth via
  `google-github-actions/auth` with `google-github-actions/setup-gcloud`.
- Produces: image tag `europe-west3-docker.pkg.dev/<project>/energy/energy-pipeline:<short-sha>`
  passed to `terraform apply -var image=...`.

**Jobs:**

1. `test` — uv sync, pytest, ruff. Runs on PRs and pushes touching
   `gcp/01-european-energy-pipeline/**`, `infra/**` or this workflow. No cloud access.
2. `plan` — WIF auth, `terraform init -backend-config=...`, `terraform plan`. PRs only.
3. `build-push` — docker build + push to Artifact Registry, tag = short SHA. Main only.
4. `apply` — needs `build-push`; protected by GitHub environment `gcp-test`
   (required reviewer = owner, configured in Task 2.3); `terraform apply`.

**Steps:**

1. Write the workflow; verify syntax locally (`gh workflow list` after push shows it).
2. Commit: `ci: energy cloud deploy workflow with WIF and environment gate`.

### Phase 1 exit check

All project checks green; `docker build` succeeds; `terraform validate` passes; PRs
merged. Nothing has contacted Google Cloud yet.

## Phase 2 — Cloud bootstrap and first deployment

### Task 2.1 Enable APIs and bootstrap WIF **[USER]**

1. Run the commands documented in `infra/BOOTSTRAP.md` with the owner's `gcloud`
   identity: create the Terraform state bucket, the `github-deployer` SA, the grant set,
   the WIF pool/provider and the `workloadIdentityUser` binding.
2. Verify: `gcloud iam workload-identity-pools describe github-pool ...` returns the
   pool; a dry-run `gcloud storage ls` with the deploy SA via
   `gcloud auth impersonate-service-account` succeeds.

### Task 2.2 GitHub configuration **[USER]**

1. Create the repository environment `gcp-test` with a required reviewer
   (the owner). This is the per-apply approval gate.
2. Add repository variables `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
   `GCP_STATE_BUCKET`.
3. Verify: the Task 1.3/1.4 PR shows a green `plan` job using WIF.

### Task 2.3 First apply

1. Merge the infra/workflow PRs after the plan job is green.
2. **[USER]** approve the `gcp-test` environment → `apply` runs.
3. Verify: `gcloud run jobs describe energy-pipeline --region europe-west3`,
   `bq ls energy`, and the bucket listing all succeed; the scheduler exists but has not
   fired yet.

## Phase 3 — Acceptance runs and evidence

### Task 3.1 First execution

1. `gcloud run jobs execute energy-pipeline --region europe-west3 --wait`; record the
   execution id.
2. Verify: raw CSV + manifest objects exist under `raw/sample/de_load/dt=.../`;
   `energy.metric_observation` has 672 rows, all keys unique; `energy.load_release` has
   one `passed` row carrying the execution id, input checksum and git sha.

### Task 3.2 Repeat execution and comparison

1. Execute the job a second time; record the second execution id.
2. Compare: identical business keys and row count (672); a reference query
   (`SELECT DATE(interval_start), COUNT(*), SUM(value) FROM energy.metric_observation
   WHERE ... GROUP BY 1 ORDER BY 1`) matches between the two runs; two release rows;
   two raw objects (no overwrite).

### Task 3.3 Scheduled execution

1. Wait for the Monday 05:15 Europe/Berlin fire (or use the scheduler's Force run once
   for evidence, noted as such in the verification doc).
2. Record the execution id of the scheduled run and its release row.

### Task 3.4 Cost and evidence write-up

1. **[USER]** read Billing → Reports for the project over the acceptance window and
   record the observed cost.
2. Write `docs/cloud-verification.md`: execution ids, window, input checksum, release
   rows, comparison results, identities used, failure handling observed, cost, and the
   scheduler evidence.
3. Update the project README ("Cloud acceptance (planned)" → recorded status) and the
   root README status table row for the energy pipeline.
4. Merge the evidence PR.

## Out of scope (design §2)

G02 API, event corrections (G03), release catalog and IAM product model (G04), training
(G05), the reusable project factory (G06), live SMARD download from cloud IPs, growing
backfills, and a historical-refresh policy. This milestone publishes one versioned
window twice and proves the path is repeatable.

## Expected cost

Cloud Run Job scales to zero between weekly executions; the sample is ~672 rows;
GCS storage is single-digit MB; BigQuery storage and query volume are far below the
free tier. Expected total ≈ €0/month. The Task 0.1 budget alert is the safety net, not
an expected spend.
