# SoloLakehouse engineering roadmap

<!-- [Codex · 2026-11-13] Git-first project scope and delivery roadmap. -->

## Position and scope

SoloLakehouse started as a self-hosted lakehouse and now organizes independent
Data & AI projects in one version-controlled repository. Aviation is the
flagship domain. Energy and finance provide separate workloads for testing
cloud delivery and data or ML reproducibility. The self-hosted project
provides an environment for platform engineering and recovery exercises.

The current branch contains project briefs and a template. Project code,
project-level CI/CD and runtime acceptance for these briefs are future
milestones. The historical self-hosted implementation and its evidence are
available in a pinned snapshot.
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

- **Aviation.** [Databricks Aviation Lakehouse](../databricks/aviation-lakehouse/README.md)
  owns the planned observation-to-feature exercise. [GCP Aviation ML
  Serving](../gcp/aviation-ml-serving/README.md) owns the planned prediction
  interface and model-version checks. Connect them when the feature and model
  contracts have verified inputs and outputs.
- **European energy.** The [GCP European Energy
  Pipeline](../gcp/european-energy-pipeline/README.md) starts with one German
  electricity-market metric in a fixed date window, with the source, unit,
  time zone and quality rules recorded.
- **Finance.** The [Local ECB Silver Pipeline](../local/ecb-silver-pipeline/README.md)
  specifies and verifies cleaned policy-rate rows. The [Databricks Financial
  ML Pipeline](../databricks/financial-ml-pipeline/README.md) starts with a
  time-ordered split and a versioned baseline.
- **Platform engineering.** The [Local Self-hosted
  Lakehouse](../local/self-hosted-lakehouse/README.md) starts with a fixture
  query in Compose. K3s, Flux and recovery remain later project milestones.

## Delivery milestones

1. **First project and scoped CI.** Use the [project
   template](../project-template/README.md) for the first energy fixture and
   tests. Verify three cases in Actions. A change inside the project runs
   its CI, an unrelated change leaves it idle, and a failing test produces
   a failed check. If checks later become required for merge, verify that
   the required result is reported on all relevant PRs.
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
