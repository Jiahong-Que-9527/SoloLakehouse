# SoloLakehouse v2.5 Operations Runbook

This runbook covers common operational tasks for the local v2.5 Compose baseline.

It is written for incident-style use: identify the failing service, run the smallest safe command, and preserve enough evidence to explain what happened.

## Quick Triage

```bash
make verify
make health
docker ps
```

Open `http://127.0.0.1:8090/health` after `make health` to use the local
operator portal. It shows entity identity, service status, demo readiness,
core UI links, and links to the demo runbooks.

## Restart One Service

Use targeted restarts when a single service is unhealthy:

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  restart trino
```

Replace `trino` with `mlflow`, `dagster-webserver`, `dagster-daemon`, `openmetadata-server`, or `superset` as needed.

Run `make verify` after every restart.

## Inspect Logs

```bash
docker logs --tail 200 slh-trino
docker logs --tail 200 slh-dagster-webserver
docker logs --tail 200 slh-dagster-daemon
docker logs --tail 200 slh-hive-metastore
docker logs --tail 200 slh-postgres
```

For a live stream:

```bash
docker logs -f slh-dagster-webserver
```

## Clean Metastore and Runtime State

Use this only when local state is corrupted or a demo must start from a clean baseline.

```bash
make clean
make setup
make demo
```

`make clean` deletes bind-mounted runtime state under `docker/data/`. It is destructive for local MinIO, PostgreSQL, Dagster, OpenMetadata, and Superset state.

## Debug a Failed Trino Query

1. Confirm Trino and Hive Metastore health:

   ```bash
   make verify
   docker logs --tail 200 slh-trino
   docker logs --tail 200 slh-hive-metastore
   ```

2. Check that Gold tables exist after the demo data-flow job:

   ```bash
   make demo
   .venv/bin/python scripts/verify-demo.py
   ```

3. If Hive succeeds but Iceberg fails, rerun Gold registration through the pipeline and inspect Trino logs.

4. If both fail, inspect MinIO paths for Bronze/Silver/Gold output before debugging Trino.

## Debug a Failed Dagster Run

1. Open `http://localhost:3000`.
2. Open the latest `demo_data_flow_job` for demo failures, or `full_pipeline_job` for full pipeline failures.
3. Identify the first failed asset or op.
4. Capture logs:

   ```bash
   docker logs --tail 300 slh-dagster-webserver
   docker logs --tail 300 slh-dagster-daemon
   ```

5. Rerun only after `make verify` is green.

## Handle Full Disk

Symptoms include Postgres write errors, MinIO write failures, failed image pulls, or Elasticsearch startup loops.

1. Check disk:

   ```bash
   df -h
   du -sh docker/data
   docker system df
   ```

2. Stop services while preserving local data:

   ```bash
   make down
   ```

3. Remove disposable Docker cache if needed:

   ```bash
   docker image prune -f
   docker builder prune -f
   ```

4. For a fully clean demo reset:

   ```bash
   make clean
   ```

## Known Demo-Safe Recovery Paths

| Symptom | Likely cause | Recovery |
|---|---|---|
| `make setup` waits for health and times out | OpenMetadata, Superset, or Elasticsearch warm-up | Wait 2-5 minutes, then `make verify`. |
| PostgreSQL auth error in Hive Metastore | stale local `docker/data/postgres` from old credentials | `make clean && make setup`. |
| MLflow UI reports host header issue | old MLflow container config | `make up`, then `make verify`. |
| Dagster artifact upload fails | missing S3 env vars in Dagster containers | `make verify` checks Dagster S3 credentials. |

## Escalation Evidence

When opening an issue or asking for help, include:

- OS and Docker version.
- `make verify` output.
- failing command and exit code.
- `docker logs --tail 200 <container>`.
- whether the environment was fresh or reused.
