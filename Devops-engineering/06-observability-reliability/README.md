# D06 · Observability and reliability

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Use service behavior and controlled incidents to validate monitoring and recovery.

## Deliverables

- Request count, error rate and latency metrics, with structured logs and readiness signals. Use Prometheus and Grafana as the planned local metrics stack.
- A documented baseline with workload and observation window, plus alerts with recovery instructions for the chosen failure scenarios.
- A procedure to restore a known-good audit input and verify its integrity. Use disposable copies for fault injection.

## Acceptance

1. Capture a healthy baseline and verify that metrics relate to actual requests and the deployed revision.
2. Exercise three scenarios such as elevated HTTP errors, a stopped workload and a corrupted audit fixture. Record alert or detection time, diagnosis, recovery procedure and recovery time.
3. Verify the quality endpoint and input checksum after each recovery. Record failed or noisy signals and update the alert or runbook based on observed behavior.

D07 uses the validated deployment checks, observability defaults and operating notes.

## Evidence

Pending implementation and acceptance runs.
