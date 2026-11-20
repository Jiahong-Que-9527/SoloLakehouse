# [李淳风·2026-11-20] Cloud Run service image for the Energy Analytics API (Task 0.1).
# Build: docker build -t energy-analytics-api:dev .
# Cloud Run injects PORT; defaults to 8080 locally.
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

# Source lands in one layer.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra cloud --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# The asgi module builds the real GCP adapter from BQ_DATASET/BQ_VIEW env vars.
CMD exec uvicorn energy_api.asgi:app --host 0.0.0.0 --port ${PORT:-8080}
