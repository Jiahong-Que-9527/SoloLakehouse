# SoloLakehouse 用户指导（v2.5）

本指南仅覆盖当前主线：**v2.5 单轨运行模式**。
历史版本（v1/v2 并行路径）已归档到 `docs/history/`。

## 1. 平台概览

SoloLakehouse 是一个可本地运行的 Lakehouse 参考实现，核心链路：

ECB/DAX 数据源 -> Bronze -> Silver -> Gold -> MLflow

当前默认组件：
- MinIO
- PostgreSQL
- Hive Metastore
- Trino（Hive + Iceberg）
- MLflow
- Dagster
- OpenMetadata
- Superset

## 2. 环境准备

要求：
- Docker + Docker Compose 插件
- Python 3.13+
- `make`

初始化：

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 启动与验证

```bash
make up
make verify
```

`make verify` 会默认检查：MinIO、PostgreSQL、Hive Metastore、Trino、MLflow、Dagster、OpenMetadata、Superset。

## 4. 运行数据管道

```bash
make pipeline
```

该命令通过 Dagster 执行 `full_pipeline_job`，是唯一支持的执行入口。

## 5. 常用 UI

| 服务 | 地址 |
|------|------|
| MinIO Console | `http://localhost:9001` |
| Trino UI | `http://localhost:8080` |
| MLflow UI | `http://localhost:5000` |
| Dagster UI | `http://localhost:3000` |
| OpenMetadata | `http://localhost:8585` |
| Superset | `http://localhost:8088` |

Superset 默认账号：`admin / admin`。

## 6. 运维清理

### 安全清理（保留数据卷）

```bash
make down
```

### 彻底清理（删除数据卷）

```bash
make clean
docker image prune -f
docker volume prune -f
```

## 7. 故障排查

1) `make up` 启动慢或超时  
- OpenMetadata/Elasticsearch 首次启动较慢，建议等待后再 `make verify`。

2) `make pipeline` 失败  
- 先执行 `make verify`，确保 Trino、MLflow、Dagster 均为 `PASS`。

3) Superset 无法登录  
- 检查 `.env` 中 `SUPERSET_ADMIN_USERNAME`、`SUPERSET_ADMIN_PASSWORD`、`SUPERSET_SECRET_KEY`。

## 8. 历史版本说明

以下内容只作为历史资料，不再作为可执行主流程：
- `docs/history/timeline.md`
- `docs/history/architecture-evolution.md`
- `docs/history/legacy-overview.md`
