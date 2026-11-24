# Lakehouse Platform Factory implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status** Template and CI validation implemented. Live deployment, isolation and retirement checks remain pending. [Brief](../README.md) · [Design](design.md) · [Runbook](runbook.md)

## First delivery

Create two isolated batch-lakehouse environments from one template. Use a one-row reference workload and the deployment and access lessons from D02 and D04.

## Implementation sequence

1. Inventory required workspace privileges, identities, compute access and state storage. Specify owner, target, resource names and expected cost signals. Map each resource to one owner: Terraform for schema and grants, Bundles for job definitions and tasks.

2. Plan stack A, validate its bundle and review the resolved target. Deploy to an isolated test environment, run the reference job and query its fixture row through the intended reader identity. Capture versions, resource IDs and elapsed onboarding time.

3. Repeat the operation with the same inputs. Verify the next plan, deployed job identity and row count. Exercise interruption between infrastructure creation and job deployment; document how a rerun completes the intended stack.

4. Instantiate B with a separate state location, schema, runtime identity and job. Verify each workload succeeds locally and that A cannot read B's Gold. Capture actual permission denials alongside positive controls.

5. Review the disposable stack inventory and proposed retirement scope. During an authorized exercise retire only that stack, re-query the survivor and distinguish shared bootstrap resources from unexpected leftovers. Record any costs still accruing.

## Portfolio evidence

Evidence: the two inventories, deploy and isolation checks, time to first verified row and retirement reconciliation. Document which onboarding decisions still need a platform operator. Link measured results from the brief after execution.
