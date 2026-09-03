FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# mlflow==3.10.1 does not pin transitive ASGI deps. Recent releases break /health:
# - starlette>=1.0 removes APIs mlflow still uses
# - anyio>=4.15 drops the top-level from_thread alias starlette's WSGI middleware needs
RUN pip install --no-cache-dir \
    mlflow==3.10.1 \
    psycopg2-binary \
    boto3 \
    "starlette>=0.40,<1.0" \
    "anyio>=4.0,<4.15"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
