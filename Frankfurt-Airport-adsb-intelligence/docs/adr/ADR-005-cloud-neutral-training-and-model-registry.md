# ADR-005: Cloud-neutral training and model registry

**Status:** Accepted.

## Context

The programme runs on a GCP trial account. Vertex AI managed training,
Vertex AI Pipelines and the Vertex AI Model Registry are not available on
it. Three designs assumed them:

- G05 (Energy Forecasting MLOps): Vertex AI Pipeline and Model Registry.
- Subproject 05 (Taxi-in Prediction): milestone M4, "Vertex AI job".
- Subproject 07 (Platform Orchestration): training listed as a cloud stage.

The MLOps capability points these projects must demonstrate —
reproducible training, version pinning, promotion gating, rollback and
traceability — are platform rules, not Vertex features. The trial
constraint removes tooling, not requirements.

## Problems and responses

| Problem | Response |
|---------|----------|
| No managed training job or pipeline runtime | Training runs locally with uv and is packaged as a container. A scheduled or remote run reuses the Cloud Run Job pattern from G01 instead of Vertex. |
| No managed model registry with aliases | MLflow provides experiment tracking and a model registry locally. Every registered version is also published as a model release manifest (release ID, git SHA, data release ID, metrics, artifact checksum) that mirrors the Gold release manifest pattern (ADR-003). |
| Registry metadata lives outside Git; a lost local database breaks the evidence chain | Artifacts go to a versioned bucket; the manifest and checksums are committed to Git. The evidence chain survives without the MLflow database. |
| Rollback semantics were delegated to registry aliases | Rollback means deploying the previous model release manifest and re-verifying; both version IDs are recorded, as the G05 design already requires. |
| Orchestration design treats training as a cloud stage | Training becomes a containerized, on-demand stage that the orchestrator triggers and observes. The Workflows-versus-Dagster ADR (subproject 07, M1) compares them under this shape. |
| Scheduled retraining and drift monitoring have no managed pipeline | The Dagster option in subproject 07 is the zero-cost orchestrator candidate. Drift stays a column in the batch evaluation report, as G05 already specifies. |
| Trial credit burn | Training stays local by default; cloud runs are small verification runs. Budget alerts from subproject 03 apply and acceptance records the observed cost. |
| Future migration to Vertex AI or another platform | Containerized training means migration changes the execution entry point only. MLflow runs map to Vertex experiments; the manifest contract is unchanged. |

## Decision

Implement the MLOps layer cloud-neutral:

1. **Tracking and registry:** MLflow, run locally, with artifacts in a
   versioned bucket when a release is published.
2. **Training:** local first, packaged as a container so the same image can
   run as a Cloud Run Job later. No design may require Vertex AI.
3. **Model releases:** every registered model version is published as a
   manifest carrying release ID, git SHA, data release ID, evaluation
   metrics and artifact checksum, following the ADR-003 release pattern.
   Rollback and serving (subproject 06) pin a manifest, not a registry
   alias.
4. **Vertex AI stays a documented migration path,** not a dependency.

## Consequences

- G05, subproject 05 and subproject 07 keep their acceptance criteria;
  only the runtime references change.
- An MLflow server is a local development tool, not an operated service.
- Model serving responses report the manifest release ID and model version.
- No managed-pipeline experience is gained while the trial account is in
  use; the revisit conditions below name when to change that.

## Revisit when

- The account gains Vertex AI access and a managed registry or scheduled
  retraining becomes worth its cost.
- Operating MLflow locally becomes a maintenance burden.
- Scheduled retraining is required before an account upgrade; evaluate the
  Dagster option in subproject 07 first.
