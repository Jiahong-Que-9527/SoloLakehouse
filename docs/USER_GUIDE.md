# SoloLakehouse 用户指南（v2.5，零到可运行）

本指南面向第一次接触本项目的用户。你可以把它理解为“照着复制命令即可跑通”的操作手册。  
当前只支持 **v2.5 单轨运行模式**，历史路径归档在 `docs/history/`。

---

## 0. 你将得到什么

按本指南完成后，你会得到一个本地可运行的 Lakehouse 平台，包含：

- MinIO（对象存储）
- PostgreSQL（元数据库）
- Hive Metastore（表元数据服务）
- Trino（查询引擎，含 Hive + Iceberg catalog）
- MLflow（实验追踪）
- Dagster（编排）
- OpenMetadata（数据目录）
- Superset（BI/查询 UI）

数据主链路：

`ECB/DAX 数据源 -> Bronze -> Silver -> Gold -> MLflow`

**EN explanation:**  
After completing this guide, you will have the full v2.5 local lakehouse stack running and verified, from raw ingestion to orchestration and ML tracking.

---

## 1. 前置条件（先检查，不要跳过）

### 1.1 需要的软件

- Docker + Docker Compose 插件
- Python 3.13+
- `make`
- `git`

### 1.2 验证命令（直接复制）

```bash
docker --version
docker compose version
python3 --version
make --version
git --version
```

如果 Docker 没启动，先启动 Docker Desktop / Docker daemon 后再继续。

**EN explanation:**  
Do not continue until these tools are installed and reachable in your shell. Most startup failures come from skipping this check.

---

## 2. 从 Git 克隆项目

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
```

建议确认你已经在仓库根目录：

```bash
pwd
ls
```

你应当看到 `Makefile`、`docker/`、`docs/`、`scripts/` 等目录/文件。

**EN explanation:**  
All commands in this guide assume you are in the repository root (`SoloLakehouse`).

---

## 3. 初始化本地 Python 环境

> 即使核心服务跑在 Docker 里，也需要本地 Python 环境来执行 `make verify` 等脚本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

可选验证：

```bash
which python
python --version
```

输出路径应指向 `.../SoloLakehouse/.venv/bin/python`。

**EN explanation:**  
The virtual environment is required for local helper scripts (especially health checks). Keep it activated in your current terminal session.

---

## 4. 配置环境变量（.env）

先准备 `.env`：

```bash
cp .env.example .env
```

本地默认值通常可直接使用，不改也能启动。  
如果你改过 PostgreSQL 用户/密码，请记得保持和 `docker/data/postgres/` 里已有集群一致（否则会出现认证失败）。

**EN explanation:**  
For first run, the default `.env` is usually enough. If you changed DB credentials previously, they must match the PostgreSQL data already under `docker/data/postgres/`.

---

## 5. 启动整个平台

### 推荐一键启动（首次）

```bash
make setup
```

`make setup` 会自动执行：

1. 检查 Docker daemon
2. 确保 `.env` 存在
3. 预拉取镜像
4. 启动全部服务并等待健康检查

首次构建镜像可能需要几分钟（尤其是 OpenMetadata/Superset 相关组件）。

### 已完成 setup 后的日常启动

```bash
make up
```

**EN explanation:**  
Use `make setup` for first-time bootstrap; use `make up` for regular restarts.

---

## 6. 健康检查（必须通过）

```bash
make verify
```

你应看到以下服务全部 `PASS`：

- MinIO
- PostgreSQL
- Hive Metastore
- Trino
- MLflow
- Dagster
- OpenMetadata
- Superset

如果有个别服务失败，先等待 10~30 秒再重试一次（部分服务启动慢于健康检查窗口）。

**EN explanation:**  
`make verify` is the gate. Continue only when all services are PASS.

---

## 7. 打开 Web 界面并确认可访问

| 服务 | 地址 |
|------|------|
| MinIO Console | `http://localhost:9001` |
| Trino UI | `http://localhost:8080` |
| MLflow UI | `http://localhost:5000` |
| Dagster UI | `http://localhost:3000` |
| OpenMetadata | `http://localhost:8585` |
| Superset | `http://localhost:8088` |

Superset 默认账号：`admin / admin`。

**EN explanation:**  
If these URLs open successfully after `make verify`, your platform is operational.

---

## 8. 运行数据管道（主流程）

```bash
make pipeline
```

该命令会在 Dagster 中执行 `full_pipeline_job`（当前唯一支持入口）。

完成后你可以再次执行：

```bash
make verify
```

然后在以下 UI 检查结果：

- Dagster UI：查看作业执行记录
- MLflow UI：查看实验/运行
- Trino UI：查看查询

**EN explanation:**  
`make pipeline` runs the end-to-end v2.5 workflow through Dagster and is the canonical execution path.

---

## 9. 日常操作（重启、停止、清理）

### 停止服务（保留数据，推荐）

```bash
make down
```

### 彻底清理（删除 `docker/data/`，危险）

```bash
make clean
docker image prune -f
docker volume prune -f
```

`make clean` 会删除本项目相关卷中的数据，下一次启动相当于“新环境”。

**EN explanation:**  
Use `make down` for normal shutdown. Use `make clean` only when you want a full reset.

---

## 10. 常见问题与直接修复

### 问题 A：`hive-metastore` 报 PostgreSQL 认证失败

现象：日志包含 `password authentication failed for user "postgres"`。  
原因：`.env` 密码与 `docker/data/postgres/` 里已初始化的 PostgreSQL 集群保存的密码不一致（或曾用过旧版 Docker 命名卷）。

修复（保留数据）：

```bash
docker exec slh-postgres psql -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
make up
make verify
```

### 问题 B：MLflow 页面报 `Invalid Host header`

现象：访问 `http://localhost:5000` 返回 DNS rebinding 提示。  
原因：MLflow allowed hosts 未包含带端口的主机头。

修复：升级到包含新默认值的最新版代码后，重建 mlflow：

```bash
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml up -d --build mlflow
make verify
```

### 问题 C：`make up` 慢或看起来卡住

首次启动 OpenMetadata/Elasticsearch/Superset 可能较慢；等待后再执行 `make verify`。

**EN explanation:**  
Most failures are startup timing or credential mismatch issues. Check service logs and rerun health verification after fixes.

---

## 11. 推荐的最短“抄作业”流程

如果你只想快速跑通，按下面执行：

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make setup
make verify
make pipeline
```

**EN explanation:**  
These commands are the minimal deterministic path from clone to a fully running stack plus one full pipeline run.

---

## 12. 历史版本说明

以下文档仅供历史参考，不是当前执行路径：

- `docs/history/timeline.md`
- `docs/history/architecture-evolution.md`
- `docs/history/legacy-overview.md`
