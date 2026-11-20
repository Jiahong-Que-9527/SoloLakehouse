# D04 · Continuous delivery

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the manifest-driven deployer and record the acceptance runs. -->

**Status:** accepted 2026-11-20 · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Implemented and accepted locally, 2026-11-20 (agent run in WSL Ubuntu,
docker via the non-default daemon socket):

- **Design:** `deploy.py` deploys from versioned manifests in
  `releases/` (`manifest-R004-*.json`). A manifest carries release ID,
  source SHA, immutable image digest, configuration revision, fixture
  checksum and the expected report identity. Runtime state lives in
  `releases/state.json` (gitignored), the append-only attempt log in
  `releases/history.jsonl`.
- **Acceptance 1 (good release):** deployed R004-001 (digest
  `sha256:45ff4ee7…`) by manifest; poll reached readiness, the served
  report identity matched the manifest, the running container's image ID
  matched the requested digest, and the deployed digest was recorded in
  `state.json` and the history.
- **Acceptance 2 (rejected candidate):** a manifest with a wrong fixture
  checksum was rejected before any state change; the running release kept
  serving 200 with the same report identity.
- **Acceptance 2 (fails after startup):** R004-002 pinned the same image
  with the malformed fixture; readiness never arrived within the 90 s
  window, the deployer rolled back automatically to R004-001, and the
  smoke check passed again on the restored release.
- **Acceptance 3 (idempotent repeat):** redeploying R004-001 verified
  again; state and history stayed consistent with two verified attempts.
- **Interruption and recovery:** a deploy of R004-003 killed after ~3 s
  left the state `deploying`; the retry with `recover` compared the
  observed runtime identity with the requested revision, matched, and
  finished verification. An earlier crash during development also proved
  the overlap guard: further deploys were refused with exit 2 until
  recovery.
- **Handoff to D05:** two verified release references —
  R004-001 (digest `sha256:45ff4ee7…`) and R004-003 (digest
  `sha256:86c6495d…`) — plus the smoke criteria: poll
  `/v1/quality/latest` on the manifest's port, expect HTTP 200 and the
  manifest's expected report identity within 90 s.

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
