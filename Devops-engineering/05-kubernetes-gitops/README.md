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
