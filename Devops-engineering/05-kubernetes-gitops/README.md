# D05 · Kubernetes and GitOps

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the chart and GitOps release path; record the acceptance runs. -->

**Status:** accepted 2026-11-20 · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

Implemented and accepted locally, 2026-11-20 (agent run in WSL Ubuntu;
k3d cluster `devops-d05`, kubeconfig context `k3d-devops-d05`):

- **Tooling pin (delivery-plan D05 decision):** k3d v5.9.0, k3s
  v1.35.5-k3s1, Helm v4.3.2, Argo CD v3.6.2. Cluster footprint: one server
  node, no agents, no ingress; access through `kubectl port-forward`.
- **Chart:** digest-pinned image, liveness `/live` and readiness `/ready`
  probes, resource requests/limits (50m/64Mi – 250m/256Mi), read-only root
  filesystem with numeric `runAsUser 10001` (the kubelet cannot verify a
  named image user), audit report provisioned as a ConfigMap. Chart
  defaults and environment values are split: `gitops-values.yaml` owns the
  release pin. Secret injection is not required in v1; when one appears it
  becomes a separate Secret resource, never this ConfigMap.
- **Acceptance 1 (bootstrap and sync):** Argo CD reconciled main
  (`bb92aef`) within ~15 s of applying the Application (Synced/Healthy);
  the D04 smoke through the cluster entry point passed (live 200, ready
  200, quality 200 with report identity `eddf-load-20260608-audit-01`).
  The trial CLI install beforehand surfaced two real diagnoses: a
  named-USER/runAsNonRoot conflict (fixed by the numeric UID) and a
  release-name versus resource-name mismatch in the smoke script.
- **Acceptance 2 (promotion through Git):** merge `22cb434` pinned digest
  R004-003 (`86c6495d…`). Argo detected OutOfSync at ~150 s (inside the
  default 3-minute refresh), auto-synced, and the rollout completed with
  the running image identity matching the new digest.
- **Acceptance 3 (drift and revert):** a manual `kubectl scale` to 2
  replicas was detected through the cluster watch and reverted by selfHeal
  in under 10 s (sync back to `Synced`, spec.replicas back to 1). The
  revert merge `a98c511` (sync revision observed as main HEAD `4b00f7d`)
  brought the running image back to `45ff4ee7…`, and the audit response
  was identical to the pre-promotion one.
- **Handoff to D06:** cluster entry point `k3d-devops-d05` (namespace
  `energy-quality`), workload labels `app.kubernetes.io/name=energy-quality`,
  `app.kubernetes.io/component=api`, known-good digest `45ff4ee7…`
  (sync revision `4b00f7d`), recovery checks: `kubectl rollout status` plus
  the port-forward smoke (ready 200, report identity match).

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
