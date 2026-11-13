# Project Template

<!-- [Codex · 2026-11-13] Initial project template. -->

Copy this directory into `gcp/`, `databricks/` or `local/` under a project
name. Replace this README with the project goal, first milestone and
reproduction steps. Add a link to the project in the repository index.

- `src/` holds ingestion, transformation, validation and the entry point.
- `tests/` holds project-specific tests and expected outputs.
- `pyproject.toml` holds Python project metadata and tool configuration.
  `requirements.txt` lists dependencies used to run the project.
- `Dockerfile` is the container build entry point.
- `.env.example` lists variable names and safe example values.
- `infra/terraform/` holds resource definitions, input variables and outputs.
- `configs/` holds non-sensitive settings for each environment.
- [Architecture](docs/architecture.md) and [Runbook](docs/runbook.md) describe
  how the project works and how to operate it.

The files are starting points. Fill in the components the project uses.
