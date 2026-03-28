FROM apache/superset:6.0.0

USER root

RUN uv pip install --python /app/.venv/bin/python --system \
    "trino[sqlalchemy]==0.336.0" \
    "psycopg2-binary==2.9.11"

COPY superset_config.py /app/pythonpath/superset_config.py
COPY init-superset.sh /app/docker/entrypoints/init-superset.sh

RUN chmod +x /app/docker/entrypoints/init-superset.sh

USER superset

ENTRYPOINT ["/app/docker/entrypoints/init-superset.sh"]
