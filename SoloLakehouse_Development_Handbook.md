# SoloLakehouse Development Handbook

*A practical Git & GitHub workflow for building, maintaining, and scaling a solo open‑source project.*

---

## 1. Purpose of This Handbook

SoloLakehouse is not a demo repository or a collection of notebooks. It is a **long‑living, production‑minded open‑source project** that reflects how modern ML / data / platform systems are built in real organizations.

This handbook defines a **clear, repeatable, low‑cognitive‑load Git & GitHub workflow** that I follow daily to:

* Keep the `main` branch always releasable
* Make every change traceable and reviewable
* Reduce mistakes and context switching
* Scale from solo development to external contributors
* Align with professional engineering and MLOps standards

This document is meant to be:

* A **daily reference** during development
* A **single source of truth** for how work is done
* A **public signal** of engineering discipline

---

## 2. Core Principles

Before the mechanics, a few non‑negotiable principles guide the workflow.

### 2.1 Issue‑Driven Development

Every meaningful change starts from an **Issue**.

* Bugs, features, refactors, docs — all are tracked
* Even solo work is documented
* History remains understandable months later

> If it is not worth an Issue, it is probably not worth committing.

---

### 2.2 Small, Reversible Changes

* Commits are **small and focused**
* Each commit should be reversible
* No “mega commits” or mixed concerns

This dramatically lowers risk and review cost.

---

### 2.3 Clean Main Branch

* `main` is always deployable
* No direct commits to `main`
* All changes go through Pull Requests

`main` represents *the truth of the system*.

---

## 3. Repository Structure Expectations

Before workflow, the repository itself follows certain conventions:

* `README.md` — project vision and usage
* `CONTRIBUTING.md` — how others can help
* `CHANGELOG.md` — human‑readable history
* `LICENSE` — explicit legal clarity
* `.github/` — issue templates, PR templates, CI

These files turn a repo into a **real open‑source project**.

---

## 4. Daily Development Workflow

### 4.1 Start of Day: Synchronize State

Every work session starts by synchronizing with `main`.

```bash
git switch main
git pull --ff-only
git status
```

Optional sanity check:

```bash
git log --oneline -n 10
```

**Goal:** start from a clean, up‑to‑date baseline.

---

### 4.2 Task Initialization (Issue → Branch)

1. Create or select a GitHub Issue
2. Decide task type:

| Type          | Prefix      |
| ------------- | ----------- |
| Feature       | `feat/`     |
| Bug fix       | `fix/`      |
| Documentation | `docs/`     |
| Refactor      | `refactor/` |

3. Create branch from `main`

```bash
git switch -c feat/example-topic
```

Each branch maps to **one Issue and one concern**.

---

### 4.3 Work Loop (Repeat Many Times)

This is the core daily loop.

```text
edit code
→ run tests / lint
→ git diff
→ git add -p
→ git commit
```

Key rules:

* Prefer `git add -p` to avoid accidental changes
* Commit messages are explicit and descriptive
* Tests or validation come before commits

Example commit message:

```text
feat: add delta table schema validation
```

---

### 4.4 Pushing and Opening a Pull Request

When a task reaches a coherent state:

```bash
git push -u origin feat/example-topic
```

Open a Pull Request on GitHub with:

* Clear title (will become final commit)
* Description of *what* and *why*
* Reference to Issue (`Closes #12`)
* Notes on testing or validation

The PR is the **official change record**.

---

### 4.5 Keeping the Branch Up‑to‑Date

If `main` moves while the PR is open:

```bash
git fetch origin
git rebase origin/main
```

or use GitHub’s *Update branch* button.

Rebasing keeps history linear and readable.

---

### 4.6 Merge Strategy

Preferred strategy: **Squash and merge**.

Why:

* `main` history stays clean
* One PR → one commit
* Easy rollback and release notes

After merge:

```bash
git switch main
git pull --ff-only
git branch -d feat/example-topic
```

Optional remote cleanup:

```bash
git push origin --delete feat/example-topic
```

---

## 5. Undo and Recovery Toolbox

Mistakes happen. These commands are part of daily safety.

### 5.1 Before Commit

```bash
git restore <file>
git restore --staged <file>
```

---

### 5.2 Fix Last Commit

```bash
git commit --amend
```

Use for:

* Fixing commit message
* Adding forgotten files

---

### 5.3 Safe Undo on Shared History

```bash
git revert <commit-sha>
```

Creates a new commit that undoes changes.

---

### 5.4 Local Hard Reset (Danger Zone)

```bash
git reset --hard <commit-sha>
```

⚠️ Only for local, unpublished commits.

---

## 6. Maintainer Daily 10‑Minute Routine

Beyond coding, maintenance keeps the project healthy.

Daily or near‑daily:

* Triage new Issues
* Label and clarify reports
* Review open PRs
* Ensure CI stays green

Weekly or per milestone:

* Update `CHANGELOG.md`
* Cut releases (Semantic Versioning)
* Improve documentation

---

## 7. Release Discipline

SoloLakehouse follows **Semantic Versioning**:

* `MAJOR` — breaking changes
* `MINOR` — new features
* `PATCH` — bug fixes

Each release includes:

* Tagged version
* GitHub Release notes
* Linked changelog entries

Releases are part of engineering credibility.

---

## 8. Why This Workflow Matters

This workflow is intentionally designed to:

* Mirror professional ML / platform teams
* Scale from solo to community
* Support audits, debugging, and reproducibility
* Serve as a personal engineering standard

SoloLakehouse is as much about **how software is built** as *what* is built.

This handbook ensures that discipline is visible, repeatable, and teachable.

---

*Last updated: 2026*
