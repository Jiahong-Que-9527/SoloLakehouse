FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
COPY --from=ghcr.io/astral-sh/uv@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv

ARG SOURCE_COMMIT
LABEL org.opencontainers.image.revision=${SOURCE_COMMIT}
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
    MODEL_RELEASE_DIR=/release PORT=8080
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev && mkdir /release
COPY app.py ./
USER 10001:10001
EXPOSE 8080
CMD ["/app/.venv/bin/python", "/app/app.py"]
