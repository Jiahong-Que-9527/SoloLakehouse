# External Validation

Every release from v2.6 onward requires at least one person **outside the
project** to run the stack on their own machine and record friction honestly.
Self-certification alone is not a release gate.

## Process

1. Pick the validation record for the target version (for example
   [`v2.6.1-external-validation.md`](v2.6.1-external-validation.md)).
2. On a machine that has **not** been used to develop SoloLakehouse, run the
   commands in the record's **Validator protocol** section.
3. Fill in environment details, pass/fail results, and every friction point —
   including steps that eventually worked after a workaround.
4. Sign the record with validator name, affiliation, and date. Do **not** commit
   secrets (`OPENMETADATA_AUTH_TOKEN`, passwords, or tokens).
5. Link the completed record from [`docs/v2.6-release-readiness.md`](../v2.6-release-readiness.md).

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
gate for a release tag.
