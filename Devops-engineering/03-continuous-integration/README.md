# D03 · Continuous integration

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

**Status:** planned · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

Verify service changes and publish an image whose source and build results can be traced.

## Deliverables

- A scoped GitHub-hosted workflow for lint, tests, image build and smoke checks. Use container scanning and attach an SBOM to the build evidence.
- A trusted publication job that runs after successful checks on the publication ref. Limit registry write access to that job. Record the image digest, commit and CI run together.
- A documented blocking policy for scan findings and failed checks, and a decision on package visibility and runtime pull access.

## Acceptance

1. Demonstrate a controlled failing change, verify the relevant check fails and confirm that run publishes no image.
2. Demonstrate a passing run for the trusted ref. Pull the resulting GHCR image by digest and verify that it returns the expected smoke-test result.
3. Record the workflow run, commit, digest, SBOM location and scan result as one release candidate.

D04 consumes an approved candidate from this workflow.

## Evidence

Pending implementation and acceptance runs.

<!-- [房玄龄·2026-11-17] Add the planned implementation sequence and portfolio evidence. -->

## Development sequence

Start with D02's image build and smoke check. Use a project-specific workflow, GHCR package and disposable candidate tag for the negative test.

1. Define the event and permission matrix. PRs run read-only checks, while a designated trusted ref may publish after checks succeed. Scope paths to this project and its dedicated workflow.
2. Run locked lint and tests. Build one candidate image and preserve its OCI artifact and checksum for the downstream jobs. Smoke-test and scan that artifact, generate its SBOM and record the severity policy used.
3. Publish the checked artifact without rebuilding it. Record the registry digest, source SHA, CI run, artifact checksum and SBOM association. Pull by digest and repeat the smoke check.
4. On a trusted test ref eligible to publish, use a unique candidate tag and deliberately fail a required check. Verify the publish job is skipped and the tag is absent. Repeat with a corrected candidate and collect both run links.
5. Hand D04 the qualified digest and evidence record. Record which checks block promotion and where the registry credential is available.

## Interview evidence

Software supply chain and delivery controls. Trace one running image back to its tested commit and explain the negative test that proves publication is conditional.
