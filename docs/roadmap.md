# SoloLakehouse engineering roadmap

<!-- [Codex · 2026-11-13] Git-first project scope and delivery roadmap. -->
<!-- [房玄龄·2026-11-17] Reconcile the roadmap with implemented aviation and energy evidence. -->

## Position and scope

SoloLakehouse started as a self-hosted lakehouse and now organizes independent
Data & AI projects in one version-controlled repository. Aviation is the
flagship domain. Energy provides a second, independently implemented workload
for testing source verification and time semantics. Finance is currently a
set of project briefs. The self-hosted implementation is available in a
pinned historical snapshot; a new fixture flow is a future milestone.

The current branch contains implemented local OpenSky acquisition and German
energy pipeline code, tests, recorded run evidence and a project-scoped energy
CI workflow. Aviation transformation, GCP and Databricks integrations, and
the other project briefs remain delivery milestones. The historical
self-hosted implementation and its evidence are available in a pinned snapshot.
[Legacy reference snapshot](https://github.com/Jiahong-Que-9527/SoloLakehouse/tree/741e6da82cdc2cad207aa6ee707b8fb157b0174a)

## Engineering boundaries

- **Engineering source of truth.** GitHub versions code, data contracts,
  infrastructure and deployment definitions, tests, architecture decisions
  and runbooks. Keep runtime data, Terraform state, credentials and model
  artifacts in the systems that own them. Link to authorized evidence from
  the project documentation.
- **Independent delivery.** A project owns its configuration, validation and
  release lifecycle. GCP, Databricks and Local are separate execution
  environments. A project can be delivered entirely within one environment.
- **Aviation data and evidence.** Use synthetic or approved data and artifacts
  for public work. The private implementation remains separately maintained.
  Document proxy-label coverage and interpretation. Claims about airport
  ground truth require independent validation.
  [Aviation reference case](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/08cfb0219cc41cb9d68e469c71dfb9a367338175/docs/workloads/aviation.md)

## Project portfolio

- **Aviation.** [Fraport ADS-B Intelligence](../Fraport-adsb-intelligence/README.md)
  collects the Frankfurt historical ADS-B record locally. Local Silver/Gold
  transformation and a versioned Gold release are the next stages. Lakehouse
  and serving work stay in that programme as
  [Aviation Lakehouse Integration](../Fraport-adsb-intelligence/04-aviation-lakehouse/README.md)
  and [Model Serving Integration](../Fraport-adsb-intelligence/06-model-serving/README.md).
- **European energy.** The [GCP European Energy
  Pipeline](../gcp/01-european-energy-pipeline/README.md) starts with one German
  electricity-market metric in a fixed date window. The
  [Energy Analytics API](../gcp/02-energy-analytics-api/README.md) and
  [Aviation Event Processing](../gcp/03-aviation-event-processing/README.md) add a
  read-only interface and a correction-handling path.
- **Finance.** The [Local ECB Silver Pipeline](../local/ecb-silver-pipeline/README.md)
  specifies and verifies cleaned policy-rate rows. The [Databricks ECB Delta
  Lakehouse](../databricks/01-ecb-delta-lakehouse/README.md) builds a versioned
  Gold product from one daily exchange-rate series.
- **DevOps delivery.** [DevOps Delivery
  Engineering](../Devops-engineering/README.md) delivers a self-contained path
  from local development through CI, release, GitOps and recovery for one
  reference service. D01–D07 are accepted with recorded evidence; D01–D02
  were accepted 2026-11-22 on a fresh GitHub checkout.
- **ML engineering.** [ML
  Engineering](../Mlops-engineering/README.md) closes one ML system end to
  end on a synthetic EV-charging workload: point-in-time features, rolling
  backtests, MLflow lineage, a release gate, serving, drift monitoring and
  Dagster orchestration. M01 (data foundation), M02 (feature pipeline with
  the leakage suite), M03 (baselines and the evaluation harness), M04
  (the model beats both baselines under full MLflow lineage) and M05
  (one idempotent training pipeline, the model release pinned through the
  promotion gate, tested rollback and a training image), M06 (idempotent
  batch scoring with committed manifests and the pinned model served over
  HTTP) are accepted;
  drift monitoring and retraining triggers are next.
- **Platform engineering.** The [Local Self-hosted
  Lakehouse](../local/self-hosted-lakehouse/README.md) starts with a fixture
  query in Compose. K3s, Flux and recovery remain later project milestones.

## Delivery milestones

1. **Implemented local foundations.** Maintain the aviation acquisition and
   energy pipeline tests, run evidence and scoped CI. Verify that an energy
   change runs its CI, an unrelated change leaves it idle, and a failing test
   produces a failed check before treating path scoping as accepted behavior.
   If checks later become required for merge, verify that the required result
   is reported on all relevant PRs.
   [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
2. **First GCP data delivery.** Expand the energy fixture into one batch
   path using a Cloud Run Job, Cloud Storage and BigQuery. Record a run ID,
   the source window, quality checks, query output and the result of a
   repeat run. Document deployment and runtime identities, failure handling
   and observed cost when a cloud environment is used.
   [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/execute/jobs)
3. **Databricks Aviation Lakehouse.** Reproduce a small batch through
   Bronze, Silver and Gold. Verify event identity, proxy coverage and the
   feature cutoff. Add job definitions and experiment tracking after the
   transformations are reproducible in an approved workspace.
   [Databricks Bundles](https://docs.databricks.com/gcp/en/dev-tools/bundles)
4. **Aviation model serving.** Version the API contract and model artifact.
   Validate the synthetic request first. A later deployment milestone
   records the served model version, predictions, logs and recovery steps.
5. **Reuse proven delivery practices.** Compare workflows from working
   projects and extract shared steps where they repeat. Keep validation,
   identities and deployment decisions scoped to each project.

The order above starts with a bounded energy delivery and gives aviation
the larger data-to-model case. Finance and Local projects can use the same
standards when their own implementation milestones are selected.

## What to document as projects mature

- **Reproducible:** State the problem, inputs, expected output, setup and
  run commands. Record fixture provenance and relevant assumptions.
- **Verified:** Record the commit, checks, CI run and data-quality evidence.
  Give failures an observable outcome and a rerun procedure.
- **Deployed:** Record the environment, configuration, artifact version and
  functional verification. Link the deployment to the source commit.
- **Operable:** Document monitoring, cost, known limitations and recovery.
  Report measured outcomes and the scope of any recovery exercise.

Use the project README as its entry point. Add architecture and runbook
details as they become necessary to reproduce or operate the project.
