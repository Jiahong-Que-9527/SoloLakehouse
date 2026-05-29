# `make demo` 详细说明与手动执行指南

本文档解释 `make demo` 到底做了什么，以及在不直接使用 `make demo` 的情况下，如何一步一步手动执行并确认通过。

适用场景：

- 第一次 cold-clone 后想确认 v2.5 数据流真的可跑。
- Demo 录屏前想知道每一步在证明什么。
- `make demo` 失败后，需要把流程拆开定位是哪一段失败。

## 1. 前置条件

执行 `make demo` 前，必须已经完成全栈启动：

```bash
make setup
```

`make setup` 会完成：

- 创建 `.env`
- 创建 `.venv`
- 安装 Python 依赖
- 拉取 Docker 镜像
- 启动 PostgreSQL、MinIO、Hive Metastore、Trino、Dagster、MLflow、OpenMetadata、Superset
- 等待所有服务健康

如果你不是第一次运行，也可以用：

```bash
make up
```

通过标准：

- 命令退出码为 `0`
- 终端最后出现 `SoloLakehouse is ready.`
- `make verify` 全部 `PASS`

## 2. `make demo` 做了什么

`make demo` 在 Makefile 中等价于三步：

```makefile
demo:
	$(MAKE) verify
	$(MAKE) pipeline DAGSTER_JOB=demo_data_flow_job
	$(PYTHON) scripts/verify-demo.py
```

换成人话就是：

1. 先确认所有服务都健康。
2. 通过 Dagster 执行 `demo_data_flow_job`。
3. 用 Trino 查询 Gold 表，确认 Hive Gold 和 Iceberg Gold 都有数据。

`make demo` 刻意不执行完整的 `full_pipeline_job`，因为完整 job 还包括 MLflow 实验训练。Demo gate 的目标是快速证明 v2.5 的核心数据流：ECB/DAX -> Bronze -> Silver -> Gold -> Trino。

## 3. 一键执行方式

推荐方式：

```bash
make demo
```

成功时你应该看到三类证据。

第一类：服务健康检查：

```text
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS
PostgreSQL       PASS
Hive Metastore   PASS
Trino            PASS
MLflow           PASS
Dagster          PASS
Dagster S3 creds PASS
OpenMetadata     PASS
Superset         PASS
```

第二类：Dagster job 成功：

```text
RUN_SUCCESS - Finished execution of run for "demo_data_flow_job".
```

第三类：Gold SQL 断言成功：

```text
Demo check      Rows  Status
--------------- ----- ------
Hive Gold       53    PASS
Iceberg Gold    53    PASS
```

行数不要求永远等于 `53`，但必须大于 `0`。如果未来数据窗口变化，行数可能变化。

## 4. 手动执行方式：拆开 `make demo`

如果你想逐步操作，而不是直接运行 `make demo`，按下面三步执行。

### 4.1 服务健康检查

```bash
make verify
```

这一步运行：

```bash
.venv/bin/python scripts/verify-setup.py
```

它检查：

- MinIO API 是否可用，且配置的数据、审计、MLflow artifact bucket 存在
- PostgreSQL 是否可连接，且必要数据库存在
- Hive Metastore 9083 端口是否可连接
- Trino `/v1/info` 是否健康
- MLflow `/health` 是否健康
- Dagster `/server_info` 是否健康
- Dagster 容器内是否有 S3 / MLflow 相关环境变量
- OpenMetadata API 是否健康
- Superset `/health` 是否健康

通过标准：

- 每一行都是 `PASS`
- 命令退出码为 `0`

如果失败，先不要继续跑 pipeline。先看失败服务对应日志，例如：

```bash
docker logs --tail 200 slh-trino
docker logs --tail 200 slh-dagster-webserver
docker logs --tail 200 slh-hive-metastore
```

### 4.2 执行 Demo 数据流 Job

```bash
make pipeline DAGSTER_JOB=demo_data_flow_job
```

这一步会进入 Dagster 容器并执行：

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  exec dagster-webserver \
  dagster job execute \
  -f /app/dagster/definitions.py \
  -j demo_data_flow_job
```

`demo_data_flow_job` 包含这些 Dagster assets：

| Asset | 作用 | 产出 |
|---|---|---|
| `ecb_bronze` | 抓取并校验 ECB 利率数据 | MinIO Bronze Parquet |
| `dax_bronze` | 读取并校验 DAX 日行情数据 | MinIO Bronze Parquet |
| `ecb_silver` | 清洗 ECB Bronze 数据 | MinIO Silver Parquet |
| `dax_silver` | 清洗 DAX Bronze 数据 | MinIO Silver Parquet |
| `gold_features` | 合并 ECB/DAX，生成事件特征，并注册 Gold 表 | Hive Gold + Iceberg Gold |

这一步还会执行 `gold_features_min_rows_check`，确认 Gold 特征数据至少有足够事件行。

通过标准：

```text
RUN_SUCCESS - Finished execution of run for "demo_data_flow_job".
```

关键日志包括：

```text
ecb_bronze - STEP_SUCCESS
dax_bronze - STEP_SUCCESS
ecb_silver - STEP_SUCCESS
dax_silver - STEP_SUCCESS
gold_features - STEP_SUCCESS
Asset check 'gold_features_min_rows_check' ... passed
```

如果失败，到 Dagster UI 查看更清楚：

```text
http://localhost:3000
```

打开最新的 `demo_data_flow_job` run，找到第一个红色 step。

### 4.3 验证 Gold 表可查询

```bash
.venv/bin/python scripts/verify-demo.py
```

这一步会用 Trino 查询：

```sql
SELECT count(*) AS total_rows
FROM iceberg.gold.ecb_dax_features;
```

通过标准：

```text
Demo check      Rows  Status
--------------- ----- ------
Iceberg Gold    <n>   PASS
```

其中 `<n>` 必须大于 `0`。

## 5. 完全手动执行方式：不使用 `make demo`

如果你想完全绕开 `make demo`，直接执行底层命令，可以这样做。

### 5.1 健康检查

```bash
.venv/bin/python scripts/verify-setup.py
```

### 5.2 Dagster job

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  exec dagster-webserver \
  dagster job execute \
  -f /app/dagster/definitions.py \
  -j demo_data_flow_job
```

### 5.3 Gold SQL 断言

```bash
.venv/bin/python scripts/verify-demo.py
```

这三条命令全部退出码为 `0`，就等价于 `make demo` 通过。

## 6. 浏览器手动确认

命令行通过后，可以用 UI 做人工确认。

### 6.1 SLH Portal

启动本地 operator/demo portal：

```bash
make health
```

打开：

```text
http://127.0.0.1:8090/health
```

确认 entity identity、核心 UI 链接、demo readiness、demo flow 和服务健康表都符合当前运行环境。服务健康全部显示 `PASS` 后，再继续执行或复核 `make demo`。

### 6.2 Dagster

打开：

```text
http://localhost:3000
```

确认：

- 最新 run 名称是 `demo_data_flow_job`
- run 状态为 success
- asset graph 中 Bronze、Silver、Gold 相关资产都已 materialized
- `gold_features_min_rows_check` 通过

### 6.3 MinIO

打开：

```text
http://localhost:9001
```

默认账号来自 `.env`：

```text
MINIO_ROOT_USER=sololakehouse
MINIO_ROOT_PASSWORD=sololakehouse123
```

确认 bucket：

- `sololakehouse`
- `sololakehouse-audit`
- `mlflow-artifacts`

确认数据路径：

- `bronze/ecb_rates/`
- `bronze/dax_daily/`
- `silver/ecb_rates_cleaned/`
- `silver/dax_daily_cleaned/`
- `gold/rate_impact_features/ecb_dax_features.parquet`

### 6.4 Trino

打开：

```text
http://localhost:8080
```

Trino UI 主要用于查看查询执行状态。实际 SQL 断言由 `scripts/verify-demo.py` 执行。

## 7. 每一步在证明什么

| 步骤 | 证明点 | 为什么重要 |
|---|---|---|
| `make verify` | 基础服务全部可用 | 避免 pipeline 失败时还要猜是 Trino、MinIO 还是 Dagster 坏了 |
| `demo_data_flow_job` | 数据能从源进入 Bronze/Silver/Gold | 证明 v2.5 不是只有容器启动，而是真的有数据流 |
| `gold_features` | Trino 能注册 Hive Gold 和 Iceberg Gold | 证明查询层和表格式边界都可用 |
| `gold_features_min_rows_check` | Gold 数据不是空表 | 防止“成功但没有业务数据”的假阳性 |
| `scripts/verify-demo.py` | Gold 表能被 Trino 查询且行数大于 0 | 证明最终消费面可用 |

## 8. 常见失败与处理

### 8.1 `make verify` 失败

先看失败服务名称。常用命令：

```bash
docker ps
docker logs --tail 200 slh-postgres
docker logs --tail 200 slh-hive-metastore
docker logs --tail 200 slh-trino
docker logs --tail 200 slh-dagster-webserver
```

如果 OpenMetadata 或 Superset 刚启动，等待 2-5 分钟后重试：

```bash
make verify
```

### 8.2 Hive Metastore 认证失败

症状通常是：

```text
password authentication failed for user "postgres"
```

这通常来自复用旧的 `docker/data/postgres`。优先尝试：

```bash
make up
make verify
```

如果仍失败，且你可以删除本地演示数据：

```bash
make clean
make setup
```

### 8.3 Dagster job 失败

打开：

```text
http://localhost:3000
```

找到最新 `demo_data_flow_job`，查看第一个失败 step。

常用日志：

```bash
docker logs --tail 300 slh-dagster-webserver
docker logs --tail 300 slh-dagster-daemon
```

### 8.4 Gold SQL 断言失败

先确认 Trino 健康：

```bash
make verify
```

再确认 demo job 已经成功：

```bash
make pipeline DAGSTER_JOB=demo_data_flow_job
```

然后重新执行：

```bash
.venv/bin/python scripts/verify-demo.py
```

如果仍失败，看 Trino 日志：

```bash
docker logs --tail 300 slh-trino
```

## 9. 通过后如何记录结果

建议记录：

```text
Command: make demo
Result: PASS
Health: all services PASS
Dagster job: demo_data_flow_job RUN_SUCCESS
Hive Gold rows: <n>
Iceberg Gold rows: <n>
Timestamp: <YYYY-MM-DD HH:MM>
Environment: <OS + Docker version + Python version>
```

最小通过结论示例：

```text
SoloLakehouse v2.5 make demo PASS.
The stack health check passed, Dagster demo_data_flow_job completed successfully,
and both Hive Gold and Iceberg Gold returned non-zero row counts through Trino.
```
