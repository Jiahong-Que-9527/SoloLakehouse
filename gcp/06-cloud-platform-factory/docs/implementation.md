# Cloud Platform Factory implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

**Status:** planned. [Project brief](../README.md) and [technical design](design.md).

## First delivery

Use the batch template and a one-row reference workload to provision two disposable environments. Capture the manual bootstrap and ownership needed before another developer can use the template.

## Implementation sequence

1. Inventory prerequisites. Select test project, billing scope, region, owners, state backend, federation provider and bootstrap administrator. Record which resources are shared and which belong to one stack. Separate deployment identity from runtime identity and specify the repository and trusted ref allowed to federate.

2. Define the batch template inputs and outputs. Allocate distinct state prefixes, resource names and identities for stacks A and B. Define a fixture object and one expected result row. Validate inputs and produce reviewable plans before applying either environment.

3. Apply A and run the smoke job. Verify its row, runtime principal and job ID. Repeat the plan with identical parameters and inspect drift. Record apply time and manual interventions. Simulate a partial apply in a disposable exercise and verify that a new plan converges safely.

4. Provision B using the same template with a second spec. Verify each identity can read its own result and fails a cross-stack read. Check deployment permissions independently of naming conventions or Terraform state prefixes. Capture the actual scope of IAM grants.

5. Retire only the selected exercise stack after reviewing its inventory and destroy plan. Query the surviving stack and list residual resources by owner, separating shared bootstrap resources from unexpected leftovers. Record budget configuration, observed costs or billing lag, and ownership of the surviving stack until retirement.

## Acceptance record

Two environment inventories, a no-change plan, cross-access tests and a teardown reconciliation. Record time to first verified job as a developer-experience measure. Use the results to decide which inputs merit reusable defaults. Link the run record from the project brief after execution and identify any checks still pending.
