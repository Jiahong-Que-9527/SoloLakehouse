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
