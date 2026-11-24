# Lakehouse Platform Factory

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D06 · Complete within Databricks Free Edition scope** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Runbook](docs/runbook.md)

Turn recurring Databricks environment and delivery work into a reusable setup for a second data team.

## Technical scope

Terraform, Unity Catalog, Declarative Automation Bundles and CI/CD.

## Input and output

- **Input.** A workload definition and role requirements from [D02](../02-financial-etl-automation/README.md) and [D04](../04-unity-catalog-governance/README.md).
- **Output.** An environment template that provisions catalog and schema resources with Terraform and deploys jobs through Bundles, with scoped permissions and onboarding evidence.

## Acceptance

1. Provision two isolated test environments from the same template and deploy a reference job into each.
2. Verify a representative team can run its own job and read its allowed data, and is denied access to the other team's data.
3. Record the owning tool for each resource, the CI deployment result and the procedure for retiring a disposable environment.

## Free Edition status

The template and CI validate two stack definitions using mocked Terraform plans and strict Databricks Bundle resolution against a local authentication stub.

| Example | State path suffix | Bundle target | Reference job |
|---|---|---|---|
| Alpha | `slh-alpha-dev/terraform.tfstate` | `dev` | `slh-alpha-dev-batch` |
| Bravo | `slh-bravo-prod/terraform.tfstate` | `prod` | `slh-bravo-prod-batch` |

The reference job completed its first publish and replay on Free Edition with one workspace identity. A blank Silver value caused both quality attempts to fail and blocked the publish task. A separate inspection found the original single Gold row. The [workspace evidence](evidence/free-edition-reference-smoke.json) records the four runs and outcomes.

The following checks are **skipped in Free Edition and excluded from project completion**.

| Skipped check | Reason |
|---|---|
| Deploy and verify both Terraform stacks with separate runtime service principals | The current workspace has one usable execution identity. Free Edition excludes the account console and account-level APIs. The D06 live deployment requires a workspace that permits both service principals and their workspace entitlements. |
| Confirm Alpha can read Alpha Gold and is denied on Bravo Gold | The test requires two independently runnable principals and positive controls against both live Gold tables. |
| Retire one stack and verify the survivor | The retirement drill depends on two live stacks with separate state and a verified surviving workload. |

The runbook retains the procedures for an approved multi-principal workspace. [Operator runbook](docs/runbook.md) · [Databricks Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
