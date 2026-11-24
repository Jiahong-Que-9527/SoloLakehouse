# Financial ETL Automation implementation plan

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->

**Status:** implemented. See the brief for CLI and GitHub Actions deployment. [Brief](../README.md) · [Design](design.md)

## First delivery

Turn a pinned D01 transformation into a scheduled, repairable workspace job. Start with a dedicated test target, a valid window, a faulty batch and the expected release for the valid input.

## Implementation sequence

1. Define the job parameters, target schema and release identity. Trace one window through ingest, transform, quality and publish. Decide how a repeat request finds an already published result.

2. Validate the dependency graph and bundle target before deployment. Run fixture tests on a PR; deploy the validated revision to the test target and record the workspace job ID, commit and runtime identity.

3. Run a known-good scheduled window. Capture task states, output counts, Delta versions and the release pointer. Use this as the comparison for the failure exercises.

4. Interrupt a transient task, then submit a duplicate-key or invalid batch that should fail quality. Verify retry behavior for the former and skipped publication for the latter. Query the previous release after failure.

5. Repair the batch, rerun the affected window and repeat that request once. Check business-key uniqueness and one accepted release for the corrected inputs. Record the backfill bounds, durations and any remaining compute or schedule.

## Portfolio evidence

Evidence: link a successful schedule, a failed quality task and a repaired release. Explain why a transient retry is safe and why retrying invalid input alone cannot repair it. Link measured results from the brief after execution.
