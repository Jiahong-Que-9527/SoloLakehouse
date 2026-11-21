# D07 · DevOps platform factory

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-21] Implement the template, onboard the freshness service and record the acceptance runs. -->

**Status:** accepted 2026-11-21 · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Turn common, proven delivery assets into a repeatable onboarding path.

## Deliverables

- A service template with configurable runtime identity, image coordinates, health checks and deployment settings. Reuse the CI workflow where supported and preserve the service-specific data contract in each service.
- Minimum onboarding documentation, configuration inputs, ownership and upgrade instructions. Consider Copier once the reusable inputs are clear.
- A second small workload that uses the template and has its own image digest and deployment identity.

## Acceptance

1. Apply the same delivery conventions to the reference service and a second workload, then record actual setup steps and elapsed time.
2. For the second workload, verify CI, image publication, deployment, health checks and metrics. Confirm a release to that workload leaves the reference service functional.
3. Record where manual edits were still needed and how to upgrade the template safely. Demonstrate the documented teardown in an isolated test environment.

Summarize the measured onboarding and recovery results alongside links to the phase evidence.

## Evidence

Implemented and accepted locally, 2026-11-21 (agent run in WSL Ubuntu,
k3d cluster `devops-d05`):

- **Template** (`template/`): delivery assets only — a pyproject/Dockerfile
  pair with the hardened D02 image recipe, a scoped CI workflow with the
  D03 four-job shape (test, build+scan, smoke, digest publish to its own
  GHCR package), the D05 Helm chart (probes, resources, numeric-UID
  security context, ConfigMap input, scrape annotations) with a
  `image.repository + image.reference` split so one chart serves both
  registry digests and local drill tags, and `instantiate.py` for
  placeholder substitution. Service contracts stay with each service.
  `template/ONBOARDING.md` documents the inputs, steps, upgrade and
  teardown procedures. Copier remains the considered upgrade path.
- **Second workload:** the Report Freshness Service was prepared as an
  independent handoff (`second-workload/`: src, tests, fixtures — a stale
  snapshot is a 200 data answer, bad input a 503, freshness gauge on
  /metrics) and onboarded through the template into
  `Devops-engineering/freshness-service` with its own package, workflow
  and chart.
- **Acceptance 1 (timing):** onboarding from the prepared handoff to a
  verified deployment with metrics took ~2h wall clock, of which ~10 min
  was CI publishing and the rest was environment incident handling
  (below). The scripted onboarding itself (instantiate, bring src, lock,
  local checks) is minutes; every deviation is listed as a manual edit.
- **Acceptance 2 (second workload delivery):** its scoped CI ran
  test/build/scan/smoke green on the PR and published
  `freshness-service` to GHCR by digest on main (release candidate
  `sha256:94efca5d…`); the chart deployed it into namespace
  `energy-freshness`; live/ready 200; the freshness route answered with
  the honest stale verdict for the June fixture against the real clock;
  Prometheus scraped `snapshot_freshness=0` without extra configuration;
  and the reference service kept serving its report identity throughout
  every drill.
- **Acceptance 2/3 (upgrade and rollback):** refreshing the snapshot
  timestamp flipped the verdict to fresh (age 1.11 h) and rolling the
  values back returned it to stale (age 3948.12 h), both verified through
  the newest pod after an explicit rollout restart.
- **Acceptance 3 (teardown):** `helm uninstall` + namespace deletion left
  no cluster residue (namespace NotFound, release list empty); documented
  residuals are the GHCR package versions, the workflow file and the
  service directory.
- **Manual edits and environment incidents that shaped the template:**
  the first template draft copied the service skeleton into a nested
  directory (layout rule added to `instantiate.py`); chart placeholders
  leaked into a cluster manifest once, so instantiation asserts no
  `__` remains; a parallel session's git operation reverted uncommitted
  fixes, so fixes are committed immediately; docker-desktop's shared
  kubectl binary was replaced mid-session (SIGBUS) and the docker CLI
  began failing I/O, so both binaries are now pinned under
  `~/.local/bin` and the recordchat client; k3d image import reported
  success while containerd had no image, so the drill switched to
  save/cp/`ctr import`; and a ConfigMap-only release does not restart
  pods (kubelet sync up to ~60 s), so the runbook mandates an explicit
  rollout restart for input-only changes. The `fixture:` versus `input:`
  values-key mismatch between the D05 naming and the D07 chart was also
  corrected in the onboarded service.

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start with the proven D03 workflow, D05 deployment settings and D06 operating checks. Use a second synthetic workload within this project, such as a report-freshness service that flags stale meter snapshots.

1. List the common inputs required for a new service, including service name, image package, entry point, probe paths, environment settings and ownership. Keep freshness rules and fixture semantics in the second application.
2. Extract only the delivery pieces already exercised. Document how to instantiate the template, run its checks, pick a template revision and apply an upgrade to an existing consumer.
3. Define onboarding timing from receiving a prepared service and its contract to its first verified deployment with metrics. Record operator steps, manual edits and elapsed time. Use the same start and end conditions for any comparison.
4. Onboard the second workload with its own package and deployment identity. Verify its release, smoke response and monitoring signals. Upgrade or roll back that workload and recheck the original service.
5. Record teardown steps and residual resources for the disposable deployment. Deliver the onboarding transcript, template revision and remaining manual decisions as the final project evidence.

## Interview evidence

Platform engineering and developer experience. Show what another service owner needs to supply, which steps the platform carries out and which manual decisions the observed onboarding still required.
