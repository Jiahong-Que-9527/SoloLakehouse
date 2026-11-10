# Governance v3 Runbook

## Purpose

This runbook operationalizes v3 governance workflows so teams can run the platform with predictable controls and incident discipline.

Primary scope:

- access change workflow
- secrets rotation workflow
- SLO breach workflow
- incident communication workflow

---

## 1) Access Change Workflow

### Trigger

- new service account or user access needed
- privilege escalation request
- role ownership transfer

### Required inputs

- requester identity
- requested scope (service/schema/table/environment)
- business justification
- requested duration (temporary/permanent)

### Steps

1. Create access-change ticket with full scope and justification.
2. Validate least-privilege baseline against current policy.
3. Approve with two-person review for production scope.
4. Apply change in `dev` first; verify intended behavior and no broader access leakage.
5. Promote change to `staging`/`production` via approved release flow.
6. Record final granted scope in access registry.

### Evidence to keep

- ticket link
- reviewer approvals
- applied policy diff
- verification output/log

### Rollback

- revert policy change to last known-good version
- re-run access validation tests
- document rollback rationale

---

## 2) Secrets Rotation Workflow

### Trigger

- scheduled rotation window
- credential leakage suspicion
- emergency revocation event

### Required inputs

- secret owner
- affected services
- cutover window
- fallback credentials policy

### Steps

1. Generate new secret in managed secret store.
2. Deploy secret update to `dev`; validate connectivity and job execution.
3. Promote to `staging`; run critical pipeline checks.
4. Promote to `production` during approved window.
5. Revoke old secret after post-deployment validation completes.
6. Update rotation log and next rotation date.

### Verification checks

- `make verify` equivalent service health checks (environment-specific)
- one full pipeline execution path

### Emergency fallback

- activate restricted emergency credential profile
- limit blast radius with temporary scope constraints
- complete root-cause investigation and forced re-rotation

---

## 3) SLO Breach Workflow

### Example SLO classes

- pipeline success rate
- asset freshness
- critical asset-check pass rate
- end-to-end latency budget

### Trigger

- alert fired from SLO policy
- repeated near-breach trend

### Steps

1. Confirm breach validity (avoid false positive from monitoring noise).
2. Classify severity (`SEV-1`, `SEV-2`, `SEV-3`).
3. Assign incident owner and start timeline log.
4. Mitigate immediate impact (re-run, rollback, traffic/trigger control, or degraded mode).
5. Resolve root cause and validate SLO recovery.
6. Produce post-incident review with prevention actions.

### Communication cadence

- `SEV-1`: every 15 minutes
- `SEV-2`: every 30 minutes
- `SEV-3`: hourly or on major state change

---

## 4) Incident Communication Workflow

### Communication channels

- internal incident channel
- stakeholder update thread
- release/change log update

### Message template

1. **What happened**
2. **Current impact**
3. **Mitigation in progress**
4. **Next update ETA**
5. **Owner**

### Closure template

- incident summary
- user/data impact window
- final root cause
- corrective actions
- preventive actions and due dates

---

## 5) Governance Review Cadence

### Weekly checks

- stale elevated permissions
- secrets nearing rotation deadline
- noisy alerts requiring threshold tuning

### Monthly checks

- SLO attainment trends
- incident pattern clustering
- runbook update needs

### Quarterly checks

- policy drift review
- ownership map completeness
- governance matrix evidence refresh (`docs/governance-v3-matrix.md`)

---

## 6) Minimum Exit Criteria for v3 Governance Operations

Before claiming v3 governance readiness:

1. Access-change flow executed with audit evidence in all target environments.
2. At least one full secrets rotation drill completed end-to-end.
3. At least one SLO breach simulation run and reviewed.
4. Incident communication template used in at least one real or drill event.
5. Governance matrix has evidence links for every governance domain.
