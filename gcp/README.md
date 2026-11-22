# Google Cloud project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->
<!-- [李淳风·2026-11-20] Link the G01 implementation plan. -->

<!-- [李淳风·2026-11-20] G02 accepted: refresh delivery status, record the post-G02 sequence and the playbook settled by the first two cloud deliveries. -->

This series explores how to deliver, govern and operate data products on Google Cloud. German electricity load provides the main dataset. The event-processing project also uses synthetic airport events.

**Cost gate (all agents):** the billing account is on a Free Trial that
expires 2027-02-11. Any operation that may cost beyond the trial credits
requires the owner's explicit approval before execution — see the
[GCP cost gate](../AGENTS.md).

**Delivered and accepted on Google Cloud** (WIF-deployed, free-tier SKUs
only, every plan run at 0 destroys):

- **G01 · European Energy Pipeline** — a Cloud Run Job publishes versioned windows to Cloud Storage and BigQuery, on demand and on a weekly schedule. [Cloud verification](01-european-energy-pipeline/docs/cloud-verification.md) · [Annual acceptance](01-european-energy-pipeline/docs/year-2025-verification.md)
- **G02 · Energy Analytics API** — authenticated FastAPI on Cloud Run over an authorized BigQuery view: caller/runtime identity split, query guards, revision rollback, bounded load check. [Cloud verification](02-energy-analytics-api/docs/cloud-verification.md)
- **G03 · Aviation Event Processing** — seeded airport and energy fixtures fold through a Pub/Sub pull consumer and one transactional BigQuery script into one current state per entity: dedup, revision ordering, conflicts, quarantine, retry recovery, crash-safe redelivery and dead-letter replay verified live. [Cloud verification](03-aviation-event-processing/docs/cloud-verification.md)

G04–G06 have design and implementation guides. The numbered list gives the
learning order; each project exercises its own bounded fixture.

## Projects in learning order

1. **G01** · [European Energy Pipeline](01-european-energy-pipeline/README.md)
   Deploy a scheduled batch job and publish a repeatable electricity-load table.
   Status: **cloud delivery accepted 2026-11-20** — [verification](01-european-energy-pipeline/docs/cloud-verification.md)
   [Design](01-european-energy-pipeline/docs/design.md) · [Implementation plan](01-european-energy-pipeline/docs/implementation.md)
2. **G02** · [Energy Analytics API](02-energy-analytics-api/README.md)
   Serve approved indicators through an authenticated, measured REST API.
   Status: **cloud delivery accepted 2026-11-20** — [verification](02-energy-analytics-api/docs/cloud-verification.md)
   [Design](02-energy-analytics-api/docs/design.md) · [Implementation plan](02-energy-analytics-api/docs/implementation.md)
3. **G03** · [Aviation Event Processing](03-aviation-event-processing/README.md)
   Test duplicate and late events, retries, dead-letter handling and replay.
   Status: **cloud delivery accepted 2026-11-21** — [verification](03-aviation-event-processing/docs/cloud-verification.md)
   [Design](03-aviation-event-processing/docs/design.md) · [Implementation plan](03-aviation-event-processing/docs/implementation.md)
4. **G04** · [Governed Energy Data Product](04-governed-energy-data-product/README.md)
   Release a quality-checked data product with access and provenance evidence.
   Status: **first governed release recorded 2026-11-21** — gate passed on real G01 output, the view serves the analyst only, and the release/withdrawal drill ran live; evidence plus the five defects fixed on the way in [cloud verification](04-governed-energy-data-product/docs/cloud-verification.md)
   [Design](04-governed-energy-data-product/docs/design.md) · [Implementation plan](04-governed-energy-data-product/docs/implementation.md)
5. **G05** · [Energy Forecasting MLOps](05-energy-forecasting-mlops/README.md)
   Train, register, batch-score and roll back a versioned model.
   Status: planned — pins a G04 product release; MLflow + containerized training per ADR-005 (see project brief)
   [Design](05-energy-forecasting-mlops/docs/design.md) · [Implementation plan](05-energy-forecasting-mlops/docs/implementation.md)
6. **G06** · [Cloud Platform Factory](06-cloud-platform-factory/README.md)
   Provision isolated environments and demonstrate repeatable deployment, cost tracking and retirement.
   Status: planned — comes last; distills the deployment evidence G01–G05 will have produced
   [Design](06-cloud-platform-factory/docs/design.md) · [Implementation plan](06-cloud-platform-factory/docs/implementation.md)

## Project handoffs and independent delivery

- **Data product and forecasting (G01 → G04 → G05).** G01's cloud publication writes a source release ID and ingestion timestamp; local Parquet and manifests remain the local path. G04 will validate that input, preserve its identity in a separately versioned product release, and expose the approved data. G05 will pin the product release for training and derive average MW from interval energy in MWh and interval duration.
- **API access (G02).** G02 delivered against its own seeded read-only view and test identities. In an integrated deployment, callers need permission to invoke the API and its runtime identity needs permission to query G04's approved view; verify those permissions separately when G04 lands.
- **Event processing (G03).** Seeded energy revisions and synthetic airport events exercise duplicate delivery, retries and replay against independently expected results. G03 owns its output table and can run alongside the batch projects.
- **Environment provisioning (G06).** The factory will reuse verified deployment patterns and exercise its batch template with a one-row reference workload. Its acceptance evidence covers two isolated environments, scoped identities and retirement.

The separate [aviation serving integration](../Fraport-adsb-intelligence/06-model-serving/README.md)
can apply G05 delivery practices to the flagship model.

<!-- [李淳风·2026-11-20] Replace the G01-era priorities with the post-G02 sequence and the delivery playbook. -->

## What's next

**Immediate operational checks**

- Monday **2026-11-23, 05:15 Europe/Berlin**: the G01 scheduler (`energy-weekly`) fires for the first time since acceptance. Verify the Cloud Run execution succeeded, the `energy.load_release` ledger gained its next row, and the run stayed inside the free tier; record the evidence in the [G01 cloud verification](01-european-energy-pipeline/docs/cloud-verification.md).
- **Cost housekeeping recorded 2026-11-22** (read-only inventory plus a scoped cleanup, agent run): Artifact Registry went from 78 to 12 image versions — each package keeps only the live push group, resolved from the running deployments (`energy-pipeline:2ef73750`, `aviation-event-consumer:6147640a`, `energy-product-publisher:703b62a2`, and the energy-api digest pin `sha256:0bebbb7a…`). The live digest was pull-verified after deletion, so scale-to-zero cold starts keep working; released layers return to the 0.5 GB free tier as async GC completes (month cost ~$0). The `billing_export` BigQuery dataset is created and waits on the console-side "Standard usage cost" toggle (not configurable via gcloud v594); spend alerts are already covered by the existing €100 and €50 monthly budgets with 50/90/100% thresholds.
- Keep the standing [cost gate](../AGENTS.md) in force for every plan and apply: expected SKUs only, 0 destroys, owner approval for anything unexpected.

**Next delivery: G05 — Energy Forecasting MLOps** (G04's first governed release was recorded on 2026-11-21; [its verification](04-governed-energy-data-product/docs/cloud-verification.md) adds the playbook's sixth pattern: a release boundary is only proven once a live drill has blocked, withdrawn and republished). G05 pins the product release line that `cand-2026-11-21-fourth` started for training.

G04 residue, to fold into a hardening pass:

1. Record `git_sha` in the publish manifest — the workflow does not set `GIT_SHA`, so the applied image tag is the de-facto revision pointer.
2. Catalog and native lineage evidence stays unavailable in the test project; manifest lineage (release → input release → checksum → image tag) is the recorded substitute.

**After G04**

- **G05 — Energy Forecasting MLOps**: pin a G04 product release for training; MLflow tracking and registry with containerized training jobs ([ADR-005](../Fraport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md)), rollback drilled the way G02 drilled revisions.
- **G06 — Cloud Platform Factory**: last. Turns the by-then-proven G01–G05 patterns (WIF pipeline, bootstrap record, environment gate, teardown) into a reusable template with two isolated environments and retirement evidence.

## Delivery playbook (settled by G01 + G02)

The repeatable path every G-project follows, written down so nothing is relearned:

1. **Bootstrap before the first merge.** Create out-of-Terraform prerequisites with `gcloud` — artifact registry, deployer IAM grants — and `terraform import` them into the project's state prefix (`gcp/<nn>-<name>`). Record the as-built in the project's `infra/BOOTSTRAP.md`. G02 did this proactively; G01's post-merge build-push incident is the reason the rule exists.
2. **Plan against the real state locally** before opening the PR: expected adds only, **0 destroys**, only SKUs the Free Trial covers. Anything unexpected stops for the owner's decision ([cost gate](../AGENTS.md)).
3. **Ship through CI.** A PR runs tests plus a plan-only job; the owner merges; the `gcp-test` environment gate requires an explicit approval before apply. Everything pins `europe-west3`.
4. **Close with evidence.** A `docs/cloud-verification.md` records what was proven — identity denials, window semantics, rollback, bounded load, bytes billed — and the README status moves to accepted. Helper scripts stay outside the repo; their results, not the scripts, are the deliverable.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

<!-- [房玄龄·2026-11-17] Clarify local evidence and planned project handoffs. -->
