FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-dagster.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dagster.txt

COPY ingestion ./ingestion
COPY transformations ./transformations
COPY ml ./ml
COPY scripts ./scripts
COPY dagster ./dagster

ENV PYTHONPATH=/app
EXPOSE 3000

CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/app/dagster/workspace.yaml"]
