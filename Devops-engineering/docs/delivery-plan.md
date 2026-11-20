# Delivery plan

<!-- [房玄龄·2026-11-17] Make the DevOps project self-contained. -->

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

## Intended outcome

Given a synthetic audit report from the reference service's own fixtures, a developer can reproduce the service locally, publish an identifiable artifact, deploy an approved revision, diagnose a failure, and recover service. The first portfolio checkpoint is D01–D03 with a fresh-checkout test record, a Compose smoke test, a failed CI run that prevents publication, and a successful build linked to its image digest.

## Sequence and handoffs

- **Checkpoint 1 · Build and publish.** D01 fixes the audit response contract and repeatable development commands. D02 packages that service and proves it can run with mounted audit data. D03 runs those same checks in CI and publishes the image consumed by D04.
- **Checkpoint 2 · Release and reconcile.** D04 proves a Compose release and rollback by digest. D05 takes the same image and smoke checks into a local Kubernetes environment. The two runtimes are isolated so their release and recovery evidence can be reproduced independently.
- **Checkpoint 3 · Operate and reuse.** D06 measures detection and recovery with controlled failures. D07 extracts the stable pieces from actual implementations and verifies them with a second service.

## Decisions and rationale

- **One service, one source tree.** All phases reuse the audit API. This makes changes in delivery behavior observable while preserving the workload.
- **Self-contained inputs.** D01 defines a versioned audit report contract and keeps synthetic examples with the reference service. A read-only runtime mount carries the same fixtures into later phases.
- **File-backed first release.** A configured report file covers the first use case. A durable query or history requirement would justify evaluating PostgreSQL and adding migration and backup acceptance.
- **WSL pulls approved images.** CI builds artifacts on GitHub-hosted runners. D04 starts with local execution against a versioned release manifest. Periodic reconciliation is a follow-up after deployment and recovery are demonstrated.
- **One immutable artifact across environments.** The commit SHA identifies source and the digest identifies the published image. Compose and Kubernetes should consume the same digest. Audit-data revisions remain separately identifiable.
- **Scoped automation.** Plan a dedicated workflow scoped to changes under this project and to its workflow file. The workflow builds from this project's own inputs and vendors no assets from sibling projects.

## Decisions to resolve by phase

- **D01** — define the initial audit JSON schema, its required fields and the synthetic fixtures used to test it. Measure the baseline test and setup run before setting time targets. The schema, fixtures, parser and routes are implemented as of 2026-11-20; the baseline timing measurement is part of the pending owner acceptance.
- **D03** — choose GHCR visibility and the least-privilege credentials needed for runtime pulls. Record the scan policy and the treatment of actionable findings. Decisions recorded 2026-11-20: public package (runtime pulls anonymous), publish credential is the job-scoped `GITHUB_TOKEN` with `packages: write`, and the scan policy blocks CRITICAL/HIGH findings with a fix available while recording the rest. First workflow run pending push.
- **D04** — choose the versioned release manifest location and define local deployment state, serialization and recovery behavior.
- **D05** — confirm the local cluster footprint and pin the chosen k3d, Helm and GitOps tooling. Argo CD is the candidate for this project.
- **D06** — derive alert thresholds and observation windows from the measured baseline, and identify a known-good audit fixture for recovery.
- **D07** — select an independent second workload and decide which template inputs are genuinely reusable.

## Operating boundary

This is a personal WSL deployment exercise and runs when the host and runtime are available. Local measurements include the test workload, runtime and timestamp. Cloud deployment, public ingress and host availability are outside this roadmap. Raw reports, credentials and internal paths stay outside published evidence.
