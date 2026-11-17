# D05 · Kubernetes and GitOps

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Move the service to a local k3d cluster and reconcile its environment from versioned Git configuration.

## Deliverables

- A Helm release definition that pins the image digest and specifies probes, requests and limits, service exposure and a reproducible fixture input.
- Git-managed deployment configuration and the local sync procedure. Argo CD is the initial candidate for reconciliation.
- A documented split between chart defaults and environment values, fixture provision and secret injection. The initial deployment is reachable from the local development environment.

## Acceptance

1. Bootstrap the local cluster and sync the known-good digest. Repeat the D04 smoke check from the cluster entry point.
2. Change the digest in Git and record the sync revision, rollout result and running image identity.
3. Introduce an allowed manual drift in the disposable cluster and observe detection and reconciliation. Revert the release in Git and confirm the prior digest and audit response.

D06 consumes the reproducible deployment and verifies observable failure modes.

## Evidence

Pending implementation and acceptance runs.

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start with D04 release references, a working Docker runtime, k3d, kubectl and Helm. Record local tool versions and the cluster resources used.

1. Create a disposable cluster and namespace. Render the chart locally for the known-good manifest. Inspect the digest, probes, resource limits, endpoint and how the synthetic report is mounted.
2. Install the rendered configuration in a trial namespace, wait for readiness and repeat the D04 smoke test. Diagnose scheduling, image pulls and report mount errors before adding reconciliation.
3. Configure the GitOps controller for this project's deployment path in a separate managed namespace. Record the desired Git revision, observed digest and the sync and health states.
4. Promote a second verified digest through Git. Change one managed replica count manually and observe detection and reconciliation under the documented sync policy. Revert the release in Git and verify the original digest and audit response.
5. Give D06 the cluster entry point, workload labels, known-good revision and recovery checks. Save one rollout, one drift event and one rollback with their observed outcomes.

## Interview evidence

Kubernetes delivery. Demonstrate how to locate a failure at the image, workload or reconciliation layer using the running state and the desired revision.
