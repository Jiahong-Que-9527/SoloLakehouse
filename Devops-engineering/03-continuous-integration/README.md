# D03 · Continuous integration

<!-- [房玄龄·2026-11-17] Initialize DevOps delivery project planning. -->

<!-- [GLM·2026-11-20] Implement the scoped workflow; record the D03 decisions and local validation. -->

**Status:** workflow implemented; acceptance runs pending push · [Roadmap](../README.md) · [Evidence guide](../docs/evidence-guide.md)

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

## Decisions

Recorded 2026-11-20:

- **Package visibility:** public on GHCR. Runtime pulls (D04 WSL, D05 k3d)
  stay anonymous. The first push creates the package private by default;
  the owner flips it to public once in the package settings.
- **Publish credentials:** the workflow's built-in `GITHUB_TOKEN` with
  `packages: write`, granted to the `publish` job only. No long-lived PAT.
- **Scan policy:** Trivy blocks CRITICAL or HIGH findings with a fix
  available (`ignore-unfixed`); all findings are kept in the non-blocking
  report, and the CycloneDX SBOM travels with the evidence pack.
- **Blocking checks:** lint, tests, image build, scan and smoke must pass;
  `publish` needs all of them and runs only on push to `main`.
- **Artifact integrity:** the image is built once, saved as a tar with its
  SHA-256, scanned and smoked from that same artifact, and published
  without rebuilding; the publish job re-verifies the checksum first.

## Evidence

Workflow implemented and validated locally, 2026-11-20 (agent run; working
tree uncommitted at record time):

- **Scenario:** workflow structure. **Command:** PyYAML parse of
  `.github/workflows/devops-service.yml`. **Observed:** triggers push,
  pull_request and workflow_dispatch scoped to `Devops-engineering/**` and
  the workflow file; chain test -> build -> smoke -> publish; publish
  gated to push on `main` and the only job holding `packages: write`;
  scan policy exit-code 1, severity CRITICAL,HIGH, ignore-unfixed.
- **Reused from D02 evidence:** the image build, route smoke and
  missing-input behavior of the same Dockerfile and fixture procedure.

Pending acceptance runs (require the push):

1. PR run: read-only checks green and no publish attempt.
2. Negative test: a deliberately failing change skips `publish` and no
   candidate tag appears; record both run links (Acceptance 1).
3. Passing `main` run: flip the package to public, pull the image by
   digest from WSL and repeat the D02 smoke procedure (Acceptance 2).
4. Record run, commit, digest, SBOM location and scan result as one
   release candidate (Acceptance 3).

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
