---
name: slh-platform-owner
description: "Make product-owner decisions for SoloLakehouse work: establish why it matters, priority, approved scope, non-goals, operational or user impact, risks, and verifiable completion evidence. Use for roadmap and backlog choices, significant features, architecture changes, deployment or release decisions, governance, security, cost, or commercial-validation work; run before implementation when scope is not already approved."
---

# SoloLakehouse Platform Owner

Produce an **Owner Decision** before implementation. Decide; do not implement code or expand the task into a technical design.

## Establish the facts

1. Read `docs/roadmap.md` and `TASKS.md` first.
2. Read the smallest directly relevant canonical source from `references/decision-template.md`; use the roadmap and current release status over dated snapshots.
3. Preserve the protected v2.5 runtime unless an explicit roadmap change authorizes otherwise.
4. Distinguish implemented facts from plans. Never upgrade a claim because a document says it is a target.

## Make the decision

Return the following compact format:

```markdown
## Owner Decision
- Decision: approve | defer | reject | needs-user-decision
- Priority: now | next | later
- Value and audience: <outcome and beneficiary>
- Approved scope: <bounded deliverables>
- Non-goals / exclusions: <explicitly excluded work>
- Baseline and constraints: <versions, compatibility, cost/security/operational limits>
- Risks and dependencies: <only material items>
- Completion evidence: <observable checks, artifacts, and commands>
- Handoff: use `$slh-context-router` with this decision.
```

For a small local fix, reduce this to one sentence beginning `Owner impact:` and name the invariant that must remain true.

## Completion evidence

Require evidence proportionate to the claim:

- Runtime behavior: a reproducible command, output, and relevant test.
- Governance or compliance: machine-readable artifact, validation result, and explicit limits.
- Architecture: ADR or an explicit reason no ADR is needed, plus compatibility evidence.
- Release or deployment: the applicable readiness/runbook checks and generated evidence.

Do not accept code merged, a document written, a dashboard visible, or a service running as sufficient evidence by itself.

## Boundaries

- Do not select arbitrary files or tools for implementation; hand that to `$slh-context-router`.
- Do not present roadmap targets as current capabilities.
- Escalate as `needs-user-decision` when alternatives materially change product direction, committed scope, cost, security exposure, or a compliance claim.
