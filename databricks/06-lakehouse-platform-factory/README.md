# Lakehouse Platform Factory

<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D06 · Deferred on Databricks Free Edition** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

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

This project is **deferred** under the Databricks Free Edition track: provisioning two isolated stacks with Terraform and proving cross-identity permission denials (`A` denied on `B`'s Gold) require Databricks Account Console access, account/workspace Terraform APIs, and multiple Service Principals — none of which exist in single-user Free Edition. It stays skipped until a multi-principal workspace is approved; see [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md).

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
