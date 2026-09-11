FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dagster.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dagster.txt

COPY ingestion ./ingestion
COPY governance ./governance
COPY transformations ./transformations
COPY ml ./ml
COPY scripts ./scripts
COPY dagster ./dagster
COPY data ./data
COPY runtime_identity.py ./runtime_identity.py
COPY storage_config.py ./storage_config.py

# Baked at image build so ML lineage still works if runtime env omits GIT_COMMIT
# (compose also passes GIT_COMMIT at runtime when Make exports it).
ARG GIT_COMMIT=
ENV GIT_COMMIT=${GIT_COMMIT}

ENV PYTHONPATH=/app
EXPOSE 3000

CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/app/dagster/workspace.yaml"]
