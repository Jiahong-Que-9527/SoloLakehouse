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
