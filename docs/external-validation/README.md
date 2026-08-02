# External Validation

The integrated release candidate after v2.9 requires at least one person
**outside the project** to run the stack on their own machine and record
friction honestly. v2.9 is **delivered on `main`**; this gate is **active**.
Self-certification remains insufficient for the integrated release gate.

## Process

1. Use the integrated validation record as the **primary** protocol:
   [`integrated-v2.9-external-validation.md`](integrated-v2.9-external-validation.md)
2. Retain the Block `J` appendix in
   [`v2.6.1-external-validation.md`](v2.6.1-external-validation.md) as a required
   evidence section (lineage + Object Lock detail).
3. Check out the signed integrated candidate. It must include Block `J`
   baseline `e534c73`; do not test tag `v2.6.1` alone because it predates Block
   `J`.
4. Bootstrap with `make init-env` — **not** `cp .env.example .env`. Place
   `OPENMETADATA_AUTH_TOKEN` in `.env.secrets`, then re-run `make init-env`.
5. On a machine that has **not** been used to develop SoloLakehouse, run every
   command in the integrated record's **Validator protocol** section.
6. Fill in environment details, pass/fail results, and every friction point —
   including steps that eventually worked after a workaround.
7. Sign the integrated record with validator name, affiliation, and date. Do
   **not** commit secrets (`OPENMETADATA_AUTH_TOKEN`, passwords, or tokens).
8. Link the completed record from [`docs/v2.6-release-readiness.md`](../v2.6-release-readiness.md).

## What counts as friction

Record anything that blocked, confused, or required undocumented knowledge:

- missing or unclear prerequisites
- commands that fail on a cold clone
- services that never become healthy within the documented timeout
- manual steps that the README does not mention
- misleading defaults or stale documentation

Silence is not evidence. If the run was smooth, say so explicitly.

## Maintainer rehearsal vs external validation

Maintainers may run an **integrated cold-clone rehearsal** on a clean VM or
container and log friction in the integrated record under **Maintainer integrated
rehearsal**. That rehearsal helps fix docs before outreach, but it **does not**
satisfy the external-validation gate for the integrated release candidate.

Historical Block `J`-only rehearsal (2026-08-01) remains in the appendix record
for context.
