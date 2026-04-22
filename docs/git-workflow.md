# Git Workflow Guide

This guide defines the default workflow for branches, commits, and pull requests in SoloLakehouse.
If you are new to Git collaboration, follow the steps in this document as written.

## Goal

Use this workflow to keep repository history:

- clear
- professional
- easy to review
- easy to roll back

## Quick Path

Use this checklist for a normal contribution:

1. Update `main`.
2. Create a new branch from `main`.
3. Make one focused change.
4. Run the relevant checks.
5. Create small, professional English commits.
6. Push your branch.
7. Open a PR using the repository template.
8. Address review comments on the same branch.
9. Merge only after checks and review are complete.

## Branch Rules

### Protected Branches

- `main` is the stable branch.
- Do not commit directly to `main`.
- Do not force-push `main` unless a maintainer explicitly approves a history rewrite.

### Create a Branch for Every Change

Each task should use its own branch.
Do not mix unrelated work in the same branch.

Recommended branch prefixes:

- `feature/<short-topic>` for new functionality
- `fix/<short-topic>` for bug fixes
- `docs/<short-topic>` for documentation-only changes
- `refactor/<short-topic>` for internal cleanup without behavior changes
- `chore/<short-topic>` for maintenance work
- `hotfix/<short-topic>` for urgent production-facing fixes

Examples:

- `feature/add-iceberg-retention-check`
- `fix/mlflow-startup-timeout`
- `docs/update-deployment-runbook`

### Start from Latest `main`

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feature/your-change
```

### Keep Branches Short-Lived

- Prefer one branch per PR.
- Prefer one PR per branch.
- If a branch grows too large or starts mixing concerns, split it.

### Sync with `main`

If `main` moves while you are working, update your branch before opening or merging a PR.

```bash
git checkout main
git pull --ff-only origin main
git checkout feature/your-change
git rebase main
```

If you are not comfortable with rebase, ask a maintainer for help before merging.

## Commit Message Rules

All commit messages must be:

- written in English
- professional and specific
- focused on one logical change
- easy to understand without extra context

### Subject Line Format

Use this format whenever possible:

```text
type: concise summary
```

Recommended types:

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`
- `ci`
- `build`
- `perf`
- `revert`

Examples:

- `feat: add OpenMetadata health check`
- `fix: pass MLflow artifact credentials to Dagster`
- `docs: clarify local deployment prerequisites`
- `refactor: remove legacy pipeline entrypoints`

### Subject Line Rules

- Use imperative mood: `add`, `fix`, `update`, `remove`
- Keep it short and concrete
- Prefer one line
- Do not end with a period
- Do not use vague text such as `update content`, `fix stuff`, or `misc changes`
- Do not use emojis, slang, or mixed-language phrasing

Good:

- `docs: add 30-minute demo runbook`
- `fix: harden MLflow container startup`
- `chore: remove obsolete local snapshot files`

Bad:

- `update content.`
- `add docs.`
- `misc fix`
- `解决问题`

### Commit Body

The commit body is optional.
Add a body when the reason is not obvious from the subject.

Use the body to explain:

- why the change was needed
- important implementation context
- follow-up work or tradeoffs

Example:

```text
fix: harden MLflow container startup

Wait for Postgres readiness before starting the MLflow server.
This avoids partial startup where the health endpoint responds before
the metadata database is fully initialized.
```

### Commit Scope

- Keep each commit focused on a single idea.
- Do not bundle unrelated code, docs, and cleanup into one commit unless they are part of the same change.
- If the branch contains several distinct steps, use several clean commits instead of one large commit.

## Pull Request Rules

### Before Opening a PR

Make sure your branch is ready for review:

- code and docs are updated together when needed
- no temporary files or secrets are included
- commit history is readable
- local checks have been run

Recommended validation for this repository:

```bash
make lint
make typecheck
make test
make verify
```

Run `make pipeline` as well if your change affects runtime flow or data processing behavior.

### Open the PR

Push your branch:

```bash
git push -u origin feature/your-change
```

Then open a PR against `main`.

Use the PR template and complete these sections carefully:

- `What changed`
- `Why`
- `Validation`
- `Checklist`

### PR Title Rules

Use a clear English title that matches the branch purpose.
It can follow the same style as a commit subject.

Good examples:

- `fix: bootstrap Postgres before MLflow startup`
- `docs: add contributor Git workflow guide`
- `feat: add Iceberg catalog configuration`

### PR Description Rules

A good PR description should tell reviewers:

- what changed
- why it changed
- how you validated it
- what areas need careful review

If the PR affects user behavior, deployment, or architecture, say that explicitly.

### Draft vs Ready for Review

Open a draft PR when:

- you want early feedback
- checks are still running
- part of the work is still in progress

Mark the PR ready for review only when:

- the scope is stable
- the branch is rebased or otherwise mergeable
- the validation steps are complete

### Keep PRs Focused

Prefer small and reviewable PRs.

- One PR should solve one problem.
- Avoid mixing refactors with feature work unless they are tightly coupled.
- Large PRs slow down review and increase merge risk.

## Review and Follow-Up

### During Review

- respond to comments clearly and professionally
- push follow-up commits to the same branch
- resolve review comments only after the issue is actually addressed

If a reviewer asks for changes, update the code and reply with a short explanation of what changed.

### Updating the Branch

If the PR falls behind `main`, sync it before merge:

```bash
git checkout main
git pull --ff-only origin main
git checkout feature/your-change
git rebase main
git push --force-with-lease
```

Use `--force-with-lease`, not plain `--force`, after a rebase.

### Merge Expectations

Before merge, confirm:

- approvals are complete
- required checks passed
- unresolved review concerns are closed
- the PR description still matches the final content

## Beginner-Friendly Example

This is the standard end-to-end flow:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b docs/add-git-workflow-guide

# make your changes

make lint
make test

git add docs/git-workflow.md docs/contributing.md docs/README.md
git commit -m "docs: add contributor Git workflow guide"
git push -u origin docs/add-git-workflow-guide
```

Then:

1. Open a PR to `main`.
2. Fill in the PR template.
3. Wait for checks.
4. Address feedback on the same branch.
5. Merge after approval.

## Contributor Checklist

Before you ask for review, confirm all of the following:

- I created a branch from `main`.
- My branch name matches the change type.
- My commits are in professional English.
- My commit messages are specific and not vague.
- My PR has one clear purpose.
- I completed the relevant validation steps.
- I updated docs if behavior or workflow changed.

## When to Ask for Help

Ask a maintainer before proceeding if:

- you need to rewrite shared branch history
- you are unsure whether to rebase or merge
- your PR mixes several unrelated topics
- the change affects architecture, release flow, or production operations

When in doubt, keep the branch small, keep the commit message clear, and ask early.
