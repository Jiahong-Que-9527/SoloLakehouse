# M07 · Monitoring, drift and retraining triggers

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Observe the system the way D06 observes services: measured thresholds, wired alerts and a drilled recovery — here for model quality, not uptime.

## Deliverables

- The `monitoring` package: a residual monitor (rolling MAE against the pinned baseline), feature-drift metrics (PSI/KS per family, thresholds derived from the M03 baseline) and prediction-distribution monitoring.
- The retraining trigger policy: drift thresholds, calendar cadence and manual override, each with a recorded decision.
- The Prometheus push path for model-quality metrics and alert rules mirroring the [D06 discipline](../../Devops-engineering/06-observability-reliability/README.md): provisional thresholds set before the baseline, re-checked against it.
- The drift drill script: inject the generator's regime change, let detection fire, execute the retraining policy and measure recovery.

## Acceptance

1. The drill runs end to end: injected shift, alert firing within the documented window, triggered retraining producing a new candidate, recovery measured and recorded per the [evidence guide](../docs/evidence-guide.md).
2. Alert rules are exercised locally (a receiver check as in D06) with both a firing and a non-firing run recorded.
3. Thresholds in force cite the baseline measurement that set them; a threshold without a recorded derivation is a defect.

M08 executes this policy through the orchestrator; the policy is the interface between the stages.
