# External Validation

The integrated release candidate after v2.9 requires at least one person
**outside the project** to run the stack on their own machine and record
friction honestly. Until v2.9 is complete, external validation is deliberately
deferred and does not pause internal development; self-certification remains
insufficient for the integrated release gate.

## Process

1. After v2.9 is complete, assemble the integrated validation record, retaining
   the Block J protocol in
   [`v2.6.1-external-validation.md`](v2.6.1-external-validation.md) as one
   required evidence section.
2. Check out the signed integrated candidate. It must include Block `J`
   baseline `e534c73`; do not test tag `v2.6.1` alone because it predates Block
   `J`.
3. On a machine that has **not** been used to develop SoloLakehouse, run the
   commands in the record's **Validator protocol** section.
4. Fill in environment details, pass/fail results, and every friction point —
   including steps that eventually worked after a workaround.
5. Sign the record with validator name, affiliation, and date. Do **not** commit
   secrets (`OPENMETADATA_AUTH_TOKEN`, passwords, or tokens).
6. Link the completed record from [`docs/v2.6-release-readiness.md`](../v2.6-release-readiness.md).

## What counts as friction

Record anything that blocked, confused, or required undocumented knowledge:

- missing or unclear prerequisites
- commands that fail on a cold clone
- services that never become healthy within the documented timeout
- manual steps that the README does not mention
- misleading defaults or stale documentation

Silence is not evidence. If the run was smooth, say so explicitly.

## Maintainer rehearsal vs external validation

Maintainers may run a **cold-clone rehearsal** on a clean VM or container and
log friction in the same file under a separate heading. That rehearsal helps
fix docs before outreach, but it **does not** satisfy the external-validation
gate for the integrated release candidate.
