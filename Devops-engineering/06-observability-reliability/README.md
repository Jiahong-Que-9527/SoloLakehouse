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

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start with the working D05 deployment and an isolated copy of its fixtures. Record the deployed digest and the expected audit identity.

1. Define separate signals for request failures, latency, readiness and audit outcome. Generate a repeatable workload with a stated rate and duration, then use the baseline to choose thresholds and observation windows.
2. Connect metrics and logs to a local dashboard and an alert receiver. Verify delivery with a controlled alert and capture the timestamps at injection, notification and verified recovery.
3. Exercise three incidents individually. Induce HTTP errors and observe error rate. Stop the workload and observe an external availability check. Mount malformed report data and observe readiness and the data-input error. Restore the known-good state between exercises.
4. Run the valid failed-audit fixture as a control. The API should remain available while its data-quality result changes. Distinguish the data-consumer notification from an availability incident.
5. For each incident record detection delay, time from detection to recovery, intervention, checksum and final response. Give D07 the monitoring defaults and the runbook changes supported by the exercises.

## Interview evidence

Operational responsibility for a data service. Use one incident timeline to explain the user impact, diagnosis and evidence of recovery. Report the actual local test conditions.
