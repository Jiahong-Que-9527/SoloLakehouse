# M08 · Orchestration with Dagster

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** planned · [Roadmap](../README.md) · [Delivery plan](../docs/delivery-plan.md)

Close the loop: schedules and triggered retraining run under Dagster, wrapping the same CLI steps so a step behaves identically with or without the orchestrator.

## Deliverables

- The `orchestration` package: Dagster assets and jobs around the M05 CLI steps — daily batch scoring, monthly scheduled retraining and the M07 drift-triggered retraining.
- The WSL deployment shape (daemon plus asset jobs or ephemeral runs) decided and recorded in the [delivery plan](../docs/delivery-plan.md).
- Run lineage: every Dagster run records its inputs (data release ID, pinned model version) and links to the MLflow run and manifest it produced.
- An orchestration failure drill: a failing step retries per policy and then surfaces; a poisoned run cannot silently skip a scoring day.

## Acceptance

1. A scheduled scoring run and a triggered retraining run complete with lineage recorded end to end: Dagster run → CLI step → MLflow run → manifest.
2. The same step produces the same outputs when invoked directly and through Dagster; divergence is a defect.
3. The failure drill shows the retry behavior and the documented escalation path when retries are exhausted.

M09 extracts this assembled loop into the reusable template.
