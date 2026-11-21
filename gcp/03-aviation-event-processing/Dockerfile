# [Kimi·2026-11-21] Cloud Run job image for the aviation event consumer.
# Build: docker build -t aviation-event-processing:dev .
# The job drains the pull subscription up to MAX_MESSAGES deliveries and exits;
# Terraform supplies the entrypoint environment (PUBSUB_SUBSCRIPTION, BQ_DATASET,
# PUBSUB_DLQ_TOPIC, MAX_MESSAGES).
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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra cloud --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "aviation_events.job"]
