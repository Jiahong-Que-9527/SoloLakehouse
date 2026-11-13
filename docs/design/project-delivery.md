# Project-scoped CI/CD design

<!-- [Codex · 2026-11-13] Project CI scope and future release design. -->

[Finance](../../projects/finance/roadmap.md) and
[Aviation](../../projects/aviation/roadmap.md) have independent ownership,
milestones and acceptance evidence. The
[project index](../../projects/README.md) locates each source of truth.
The public [CI](../../.github/workflows/test.yml) runs on branch pushes and
pull requests. The [scope selector](../../scripts/ci_scope.py) maps changed
paths to Finance checks and to either Aviation or repository documentation
checks. The [Compose Demo](../../.github/workflows/compose-demo.yml) stays
manual. Release steps below describe future work.

## Trigger and change range

- **Development branch push:** Run fast checks for the affected project set.
  Compare the push's before and after commits to cover all commits in the push.
  For a new branch, use a verified merge base with the default branch when
  available. Unavailable history or ambiguous ancestry selects broad CI.
  Branch pushes have no deployment credentials.
- **Pull request:** Compare the PR head with its merge base against the target
  branch. Always start the PR workflow and always report the same required
  result. Run applicable checks without cloud or private release credentials.
  An applicable failure, cancellation or unexpected skip fails the required
  result. A deliberately inapplicable job may be skipped.
- **Future release on update to protected `main`:** Re-evaluate the full before/after range.
  Build immutable artifacts only for projects with release-affecting changes.
  Deploy selected artifacts only to configured targets through the appropriate
  deployment identity and environment controls. Ambiguous release impact needs
  review before dispatch. Documentation-only changes run validation.
- **Change classification:** Include deleted paths and both sides of a rename.
  Shared or unclassified paths and unavailable diffs select full CI. Ignore
  branch-deletion events.

Avoid filtering out the entire required PR workflow. GitHub can leave a
path-filtered required check pending. The workflow reports a stable `checks`
result after the selected jobs. Enforcing that result at merge requires
configuring and verifying the repository ruleset. See [GitHub required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

## Ownership and affected paths

| Change | Validation | Release |
|---|---|---|
| Public Finance runtime or contract | Cover current files in `ingestion/`, `transformations/`, `dagster/`, Finance ML, Finance contracts in `governance/datasets/`, and future Finance runtime paths. Run the applicable Finance tests and checks. | On main, build and release Finance only if the change affects a configured target. |
| Public project documentation or Aviation case | Validate repository docs, project links and anchors. | No release. |
| Private Aviation code, contracts or tests | The private repository receives the push and PR events. It runs fixture, ingestion, event, feature and contract checks. | The private repository releases a reviewed artifact to an isolated Aviation target. |
| Shared runtime code, dependencies, build files, validation or workflow definitions | Check all affected local consumers. Default to full repository CI for unmapped or ambiguous impact. | Evaluate each configured consumer's runtime impact independently. |
| Shared interface consumed by private Aviation | Publish or identify a versioned public interface. Design private compatibility verification against that explicit version in the private repo. | A public SLH push does not deploy private Aviation. Any future cross-repository trigger needs separately designed authorization and a private execution boundary. |

The implementation mapping must also cover tests, fixtures, configuration and
root dependency files. Test-only changes validate their consumers without
publishing artifacts. Keep the mapping aligned with actual import and build
dependencies. Public Aviation documentation and synthetic fixtures have
separate ownership from the private implementation.

The current layout keeps project ownership and navigation under
`projects/finance/` and `projects/aviation/`. Finance CI also follows the
existing root-level runtime and contract paths. Shared code, tests, build
configuration and unfamiliar non-documentation paths keep full validation.
Run the same project entry points locally with `make -C projects/finance
check` (after installing the reference dependencies) and
`make -C projects/aviation check`. Aviation-only Markdown uses the scoped
link checker. The repository docs check includes both project trees. Add new runnable
components and their dependency paths to the selector and tests when they
are introduced.

## Deployment and evidence

Use separate release identities and environment settings for each target.
For Local, CI publishes a pinned image and Flux reconciles reviewed GitOps
configuration. OpenTofu owns virtual infrastructure changes. For GCP, keep
infrastructure planning separate from workload deployment and use short-lived
federated identity. For Databricks, Bundles own workspace workload deployment;
workspace infrastructure has a separate lifecycle. Aviation deployment
definitions and evidence stay in the private project.

Capture repository, project, source SHA, contract and fixture versions,
artifact digest or package identity, deployment configuration and target,
run ID, validation result and rollback reference. Public Git can index
sanitized results. Logs, credentials, runtime data, state and backups retain
their respective operational owners. Keep release rollback and state recovery
as separate exercises.

## Acceptance scenarios

| Scenario | Expected result |
|---|---|
| Finance code or Finance contract only | Finance checks run. A reviewed release-affecting merge selects Finance and the affected configured target only. |
| Aviation implementation only | Push to the private repository triggers Aviation checks. A reviewed release selects Aviation only. Public SLH receives no private code or release data. |
| Shared dependency or public interface | Run checks for all affected SLH consumers. Verify private Aviation compatibility from its own repository when that consumer is in scope. |
| Documentation only | Docs and link checks report success with no artifact build or release. Include public Aviation docs and both project roadmap links. |
| Applicable check fails, is cancelled or unexpectedly skipped | Required PR result fails and merge is blocked by repository rules. No downstream deployment occurs. |
| Mixed code changes, rename, deletion or multiple commits | Classify the union of affected paths and consumers. Verify both old and new ownership for a rename. |
| Missing base or unknown ownership | Expand CI, record the reason and review the release target before publishing. |
| Valid reviewed release | Verify a runtime result, trace it back to the reviewed SHA and artifact, and exercise compatible rollback in isolation. |
