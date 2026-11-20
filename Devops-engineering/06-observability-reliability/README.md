# D06 · Observability and reliability

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the metrics stack and incident drills; record acceptance evidence. -->

**Status:** accepted 2026-11-20 · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Implemented and accepted locally, 2026-11-20 (agent run; k3d cluster
`devops-d05`, monitoring namespace `monitoring`):

- **Stack:** service v0.2.0 serves `/metrics` (request counters per route
  and code, latency histogram, `audit_coverage_result` gauge keyed by
  report id) via PR #195; the stack is `prometheus-community/prometheus`
  (server + alertmanager) and `grafana` from `monitoring-values.yaml`, with
  alerts routed to a host webhook receiver (`receiver.py`) writing JSONL
  evidence. Grafana is reachable via port-forward with a provisioned
  Prometheus datasource.
- **Acceptance 1 (baseline):** 555 requests at ~9.2 rps for 60 s against
  the production release; Prometheus recorded exactly 555 200s on the
  quality route (0 503s); p95 latency 4.75 ms; both pods reported
  `audit_coverage_result 1`; deployed revision cross-checked
  (`sha256:05f2f8f0…`, the v0.2.0 promotion). Baseline verdict: the
  500 ms latency and 0.2/s error-rate thresholds are far above observed
  behavior and stay as provisional-with-headroom.
- **Acceptance 2 (three scenarios, disposable trial copy):**
  - *Elevated HTTP errors:* corrupted fixture in the trial ConfigMap
    (injected 22:32:32Z), 432 requests driven at 5 rps; the
    `EnergyQualityServerErrors` critical reached the webhook in ~100 s.
  - *Stopped workload:* trial scaled to 0 at 22:36:29Z; the external
    availability check failed (000) and `EnergyQualityTrialAbsent`
    reached the webhook in ~5 s (cluster-watch detection, not the 3-minute
    Git poll).
  - *Corrupted audit fixture (valid JSON, observed 200 > expected 96):*
    the pod served 503 after 35 s of ConfigMap propagation delay; the
    `EnergyQualityAuditFailed` warning arrived at 22:42:19Z with zero
    availability alerts firing.
- **Control (valid failed audit):** the 95/96 fixture returns HTTP 200
  with `coverage_result=failed` while the gauge drops to 0; Prometheus
  fired `EnergyQualityAuditFailed` at ~80 s (starts_at 22:52:19Z) and the
  webhook received it 10 s later, with zero availability alerts firing -
  the data-quality signal is cleanly separated from an outage.
- **Acceptance 3 (recovery checks and runbook updates):** every incident
  ended with the checksum-verified restore procedure (`restore_trial.py`,
  semantic checksum `1e8536e8…` matching the fixture) and a 200 quality
  response. Observed noise that changed the alerts and runbook:
  1. A cross-namespace `min(up)` masks a single stopped namespace and
     `absent()` only fires when no series match at all - availability now
     uses a per-pod `up == 0` rule plus a per-namespace absence rule.
  2. `scale --replicas 0` removes the scrape target, so only the absence
     rule can see it.
  3. ConfigMap content propagates to pods with up to ~60 s of kubelet
     delay; recovery must restart the pod and poll the response until the
     new content is actually served.
  4. `kubectl port-forward` binds to one pod: recreate it after rollout
     restarts and kill stale forwarders (stale forwards produced misleading
     `[000]` results during the drills).
  5. One receiver process per evidence file; kill old receivers between
     drills (one control run delivered into the previous file, recorded as
     such).

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
