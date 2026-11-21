FROM python:3.13-slim

# Install with uv and remove pip so its vendored packages never appear in
# vulnerability scans; keep the base image at the Debian patch level.
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

EXPOSE __PORT__
ENTRYPOINT ["/app/.venv/bin/uvicorn", "__PACKAGE__.app:app", "--host", "0.0.0.0", "--port", "__PORT__"]
