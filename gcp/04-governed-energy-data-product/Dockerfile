# [Kimi·2026-11-21] Cloud Run job image for the governed publish job.
# Build: docker build -t governed-energy-data-product:dev .
# The job reads the G01 input release, runs the contract gate and publishes;
# Terraform supplies the entrypoint environment (BQ_DATASET, INPUT_RELEASE_ID,
# CANDIDATE_ID, CONTRACT_FILE, GIT_SHA, APPROVER).
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

COPY src ./src
COPY contracts ./contracts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra cloud --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "energy_product.publish_job"]
