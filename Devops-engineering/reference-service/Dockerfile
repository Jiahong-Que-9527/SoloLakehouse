FROM python:3.13-slim

# The runtime installs with uv and never uses pip. Removing it also removes
# pip's vendored msgpack/urllib3/setuptools, the only vulnerable packages
# trivy finds in the base image (D03 scan policy, 2026-11-20).
# Apply the Debian security patch level so OS findings have no fixed
# counterpart left at build time.
RUN pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip* \
    && apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

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

EXPOSE 8000
ENTRYPOINT ["/app/.venv/bin/uvicorn", "energy_quality.app:app", "--host", "0.0.0.0", "--port", "8000"]
