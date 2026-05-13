# Troubleshooting

> Common problems you may hit during local setup. Operational runbook lives in [`RUNBOOK.md`](https://github.com/Jiahong-Que-9527/SoloLakehouse/blob/main/RUNBOOK.md).

## Startup

### `make up` hangs or fails
<!-- TODO: Docker daemon / network / disk -->

### Port already in use
<!-- TODO: 列出占用端口 + 排查命令 -->

### Out of memory / container OOMKilled
<!-- TODO: Docker Desktop 内存上限调高 -->

### Docker image pull is too slow
<!-- TODO: registry mirror -->

## Services

### Trino not reachable on :8080
<!-- TODO -->

### Hive Metastore container restarts in a loop
<!-- TODO: Postgres 未就绪 / envsubst 模板问题 -->

### OpenMetadata stuck at "starting"
<!-- TODO -->

### Superset login fails
<!-- TODO -->

### MLflow shows no experiments
<!-- TODO -->

## Pipeline

### `make pipeline` fails at ingestion
<!-- TODO: ECB API / 网络代理 -->

### Bronze written but Silver/Gold empty
<!-- TODO -->

### Iceberg Gold table not visible in Trino
<!-- TODO -->

## Cleanup

### How do I fully reset?
<!-- TODO: make clean + 手动清残留 -->

### Disk filling up
<!-- TODO: docker/data 体积排查 -->
