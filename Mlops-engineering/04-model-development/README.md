# M04 · Model development and experiment discipline

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** planned · [Roadmap](../README.md) · [ADR-005](../../Fraport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md)

Train the supervised model under full lineage: every run traceable to a data release, a fold plan and a commit, with the baseline as the gate.

## Deliverables

- The `training` package: a gradient-boosted model (LightGBM or sklearn HistGradientBoosting, decided in the [delivery plan](../docs/delivery-plan.md)) behind an sklearn Pipeline, with the budgeted seeded search chosen at this stage.
- MLflow tracking per [ADR-005](../../Fraport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md): params, metrics, artifacts and the tag schema (data_release_id, git_sha, fold plan) on every run.
- Residual analysis and feature-importance review committed as a report, including per-segment error against the M03 baseline.
- The model card draft for the candidate, from the [template](../docs/model-card-template.md).

## Acceptance

1. The candidate beats the seasonal-naive baseline on the held-out folds under the M03 protocol, or the report documents why it does not and what would change that.
2. Every MLflow run carries the full tag schema; a run without them cannot be reproduced.
3. The segment table shows where the model wins and loses against the baseline; no segment regresses silently.

M05 registers the winning candidate; this stage does not publish a release.
