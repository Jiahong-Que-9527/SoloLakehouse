# M04 · Model development and experiment discipline

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** accepted (2026-11-22) · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md) · [Acceptance record](evidence/m04-acceptance.md) · [Model report](evidence/model-report.md) · [Model card draft](model-card-draft.md)

Train the supervised model under full lineage: every run traceable to a data release, a fold plan and a commit, with the baseline as the gate.

## Deliverables

- The `training` package (implemented as `charging_forecast.training`): a sklearn `HistGradientBoostingRegressor` behind a ColumnTransformer pipeline — decided in the [delivery plan](../docs/delivery-plan.md) over LightGBM for bit-reproducible fits — with the fixed seeded grid search and the internal selection split chosen at this stage.
- MLflow tracking per [ADR-005](../../Frankfurt-Airport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md): params, metrics, artifacts and the tag schema (data_release_id, feature_release_id, git_sha, fold plan) on every run, in a local sqlite store (gitignored).
- Residual analysis and feature-importance review committed as a report, including per-segment error against the M03 baseline.
- The model card draft for the candidate, from the [template](../docs/model-card-template.md).

## Acceptance

1. The candidate beats the seasonal-naive baseline on the held-out folds under the M03 protocol, or the report documents why it does not and what would change that. — **Met: pooled MAE 6.353 kWh vs 9.152 (naive) and 7.690 (median), both paired CIs exclude zero, all 23 folds won against the median.**
2. Every MLflow run carries the full tag schema; a run without them cannot be reproduced. — **Met: verified programmatically across all tracked runs.**
3. The segment table shows where the model wins and loses against the baseline; no segment regresses silently. — **Met: every district, station and hour improves over the station median.**

M05 registers the winning candidate; this stage does not publish a release.
