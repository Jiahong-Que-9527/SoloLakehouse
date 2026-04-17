# v3 Release Checklist

Use this checklist before tagging `v3.0.0`.

## 1) Infrastructure and environment readiness

- [ ] `dev` environment deployment is reproducible from IaC + chart/manifests.
- [ ] `staging` environment deployment is reproducible from the same release artifact set.
- [ ] Environment promotion path (`dev -> staging -> production`) is documented and validated.
- [ ] Rollback from current release to previous stable release has been tested.

## 2) Security and governance readiness

- [ ] Secrets are sourced from managed secret flow (no production static `.env` assumptions).
- [ ] Least-privilege access model is documented and applied to critical services.
- [ ] Access changes are auditable (ticket, reviewer, applied diff, verification evidence).
- [ ] Dataset governance contracts exist for key Gold and critical Silver outputs.

## 3) Reliability and observability readiness

- [ ] SLO definitions are documented for critical pipeline outcomes.
- [ ] Alert rules are enabled for SLO breaches and critical pipeline failures.
- [ ] Dashboards exist for orchestration success rate, freshness, and quality-check pass rate.
- [ ] At least 3 incident runbooks are tested via drills.

## 4) Pipeline and product validation

- [ ] v2.5 single-track pipeline path succeeds in target environment.
- [ ] Gold data quality checks pass with expected thresholds.
- [ ] ML experiment workflow produces auditable run metadata.

## 5) Documentation and release metadata

- [ ] `docs/roadmap.md` version status aligns with release intent.
- [ ] `docs/history/timeline.md` and `docs/history/architecture-evolution.md` are updated.
- [ ] `docs/history/v3-planning.md` has final decision and carry-forward notes.
- [ ] ADR index and v3 ADR set are up to date.
- [ ] `CHANGELOG.md` contains v3.0.0 release notes.

## 6) Final go/no-go decision

- [ ] All critical checklist items are complete or explicitly waived with approver sign-off.
- [ ] Release owner and rollback owner are assigned.
- [ ] Go/no-go meeting notes are recorded.
