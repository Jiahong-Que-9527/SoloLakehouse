# [李淳风·2026-11-20] Cloud Run job image for the energy publisher (Task 1.2).
# Build: docker build -t energy-pipeline:dev .
# The job command is supplied by Terraform: publish-cloud --mode sample --from ... --until ...
FROM python:3.12-slim

# Pinned uv, matching the lockfile in CI (see .github/workflows).
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Dependencies first: this layer is cached independently of the source tree.
# README.md is included because hatchling reads it as package metadata.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra cloud --no-install-project --no-dev

# Source and package data (src/energy_pipeline/data/*.csv) land in one layer.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra cloud --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["energy-pipeline"]
