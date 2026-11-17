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

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start with the qualified D03 digest, read access to its package, the smoke procedure and an isolated WSL Compose runtime.

1. Define a release manifest containing release ID, source SHA, immutable image digest, configuration revision and fixture checksum. Resolve and verify each input before changing the running deployment.
2. Serialize release attempts. Capture the last verified manifest and prepare the requested revision. Deploy and poll readiness within a stated timeout, then check report identity and counts. Mark the release verified only after both checks pass.
3. Exercise three outcomes in order. Publish a good release, reject an invalid manifest before deployment, then deploy a valid candidate with an unusable configuration. For the third case restore the prior image, config and fixture together and repeat the smoke check.
4. Repeat the same release request and simulate interruption before verification. On retry, compare observed runtime identity with recorded state and finish verification or restore the last verified manifest. Document the recovery procedure if rollback also fails.
5. Hand D05 two verified release references and the exact smoke criteria. Save a deployment history with attempt time, requested and actual revisions, last good release and recovery duration.

## Interview evidence

Release ownership. Walk an interviewer through a failed change and show the observation that established recovery for both the service and its data input.
