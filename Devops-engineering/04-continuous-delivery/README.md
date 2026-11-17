# D04 · Continuous delivery

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Deploy a qualified image into an isolated local Compose environment and exercise recovery by digest.

## Deliverables

- A versioned release manifest that carries the approved image digest and source revision. Track runtime configuration and audit input revision separately.
- A locally invoked deployment procedure that checks manifest validity, prevents overlapping releases and records the previously verified revision.
- Post-deployment smoke checks and an explicit rollback path. Introduce polling for approved manifests only after the manual release path works end to end.

## Acceptance

1. Deploy a known-good candidate from GHCR by digest into the WSL runtime, verify the audit identity and record the deployed digest.
2. Exercise a rejected candidate and a candidate that fails after startup. Verify the latter restores the prior verified digest and passes the same smoke check.
3. Repeat an already applied release and check that state and history remain consistent. Record evidence for success, failure and recovery.

D05 reuses the image, approval identity and smoke criteria.

## Evidence

Pending implementation and acceptance runs.
