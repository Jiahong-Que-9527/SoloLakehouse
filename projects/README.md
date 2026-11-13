# Projects

<!-- [Codex · 2026-11-13] Project navigation and ownership. -->

SoloLakehouse tracks its public projects and case studies here. Each entry
identifies the source of truth, reproduction path, and verified or planned
environments.

- [Finance](finance/README.md) is the public reference workload. This repository
  owns the Finance reference code, dataset contracts, tests, and Compose
  definitions. The project page links to the reproduction path and its current
  limitations.
- [Aviation](aviation/README.md) is a separately operated workload.
  This repository owns the public case description. Its private implementation,
  data, and operational evidence stay with that workload. The public case links
  to the available evidence and describes the limits of reproduction.

<!-- [Codex · 2026-11-13] Project roadmap and delivery design navigation. -->

Each project has its own learning and delivery roadmap. See the
[project CI/CD design](../docs/design/project-delivery.md) for shared trigger
rules and acceptance scenarios.

## Project checks

[GitHub Actions](../.github/workflows/test.yml) selects checks on branch
pushes and pull requests. [Finance](finance/README.md) code and contracts
run Finance reference checks. [Aviation](aviation/README.md) public docs
have their own link check. Run these checks locally with
`make -C projects/finance check` or `make -C projects/aviation check`.
Shared and unclassified changes run the complete set. The [path and release design](../docs/design/project-delivery.md)
explains ownership and future deployment.

## Managing projects in this repository

Give each project a page that identifies its engineering source of truth.
Record its scope, canonical code and contracts, test and reproduction entry
points, and environment status. Link to existing sources so that each artifact
has one maintained definition. For a separately maintained workload, link to
its public case page and identify where ownership sits.

The [roadmap](../docs/roadmap.md) defines repository scope.
[TASKS.md](../TASKS.md) holds the active work and acceptance criteria, including
project work. The [v3 construction plan](../docs/design/v3/README.md) describes
the shared infrastructure, bootstrap, deployment, and GitOps responsibilities.
