# SoloLakehouse

<!-- [Codex · 2026-11-13] Initial project layout. -->

This repository organizes independent projects by the platform where they run.

- **Google Cloud Platform** · [project1](gcp/project1/README.md), [project2](gcp/project2/README.md), [project3](gcp/project3/README.md)
- **Databricks Platform** · [project1](databricks/project1/README.md), [project2](databricks/project2/README.md), [project3](databricks/project3/README.md)
- **Local data platform** · [project1](local/project1/README.md), [project2](local/project2/README.md), [project3](local/project3/README.md)

## Project layout

Keep a project's code, tests, dependencies and deployment definitions in its own directory. Add a new project under its platform with a lowercase directory name and a `README.md` describing how to use and verify it.

## GitHub Actions

[Project CI](.github/workflows/project-ci.yml) reads the changed Git paths on a branch push or pull request. A change inside one project runs that project's job. Changes in multiple projects run one job per affected project. Changes to shared CI scripts or workflows run all projects. Root documentation changes leave project jobs skipped. A change range that cannot be resolved also runs all projects.

Each selected job checks that the project has a nonempty README. When a project provides a `ci.sh`, the job runs it with Bash from the project directory. Use that script for project-specific tests, lint or builds.

Project deployment workflows belong in `.github/workflows/`. Add a separate workflow when a project's deployment target and permissions are ready, with a path filter for the project and its deployment inputs.
