# Cloud Platform Factory

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G06 · Complete (2026-11-23)** — two stacks applied through WIF, isolation proven by a 403 cross-read, both stacks destroyed with zero residuals. Evidence: [acceptance record](evidence/g06-acceptance.md). · [Google Cloud roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

Use experience from deployed GCP workloads to provide a documented way to provision, deploy, verify and retire isolated test environments.

## Technical scope

Terraform, Workload Identity Federation, GitHub Actions, IAM and cloud cost tracking.

## Input and output

- **Input.** An environment definition and one small reference workload. Compare deployment needs from [G01](../01-european-energy-pipeline/README.md) and [G02](../02-energy-analytics-api/README.md).
- **Output.** A reusable environment template, an opt-in deployment and teardown workflow, scoped identities and provisioning, smoke-test and cost evidence.

## Acceptance

1. Provision two isolated test environments with the same template and verify that their workloads and identities are scoped independently.
2. Deploy from GitHub Actions using short-lived credentials. Record resources, ownership, expected costs and available spending signals.
3. Verify teardown of the selected disposable environment and inventory remaining resources. Retain the second environment as a check on scope.

[Identity federation for deployment pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)

## Preview teardown

From the repository root, run
`bash gcp/06-cloud-platform-factory/infra/preview-teardown.sh alpha`
(or `bravo`) with Terraform and Google Cloud credentials for the G06 state
backend. The script reads the selected stack's state and prints a destroy plan;
it does not apply it. Do not run it during another operation on the same stack.

Review the plan before separately dispatching `destroy` for that same stack in
the [G06 workflow](../../.github/workflows/g06-factory.yml). Destroying a G06
stack removes its disposable data. The preview does not target legacy
workloads, the shared state bucket, or the billing export dataset. Review the
workflow's residual inventory after the approved teardown.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->
