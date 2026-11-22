# Training image for the charging-forecast reference workload (M05).
# Base images are pinned by digest (delivery plan, M05 decision): python
# 3.13-slim and the uv 0.13.9 standalone binary, matching the CI setup-uv.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

# Install with uv and remove pip so its vendored packages never appear in
# vulnerability scans; keep the base image at the Debian patch level.
RUN pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip* \
    && apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

ENTRYPOINT ["/app/.venv/bin/charging-forecast"]
