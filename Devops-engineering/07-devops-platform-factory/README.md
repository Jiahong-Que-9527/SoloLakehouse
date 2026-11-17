# D07 · DevOps platform factory

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Pending implementation and acceptance runs.
