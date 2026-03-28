# SoloLakehouse 用户使用指导书

> 从下载到完整体验，逐步带你跑通一个生产级思路的 Lakehouse 数据平台。

---

## 目录

1. [SoloLakehouse 是什么](#1-sololakehouse-是什么)
2. [环境准备](#2-环境准备)
3. [安装与启动](#3-安装与启动)
4. [验证平台就绪](#4-验证平台就绪)
5. [v1 体验：线性脚本管道](#5-v1-体验线性脚本管道)
6. [v2 体验：Dagster 资产编排](#6-v2-体验dagster-资产编排)
7. [探索平台 UI](#7-探索平台-ui)
8. [完整命令速查](#8-完整命令速查)
9. [v3 规划预览](#9-v3-规划预览)
10. [常见问题与排障](#10-常见问题与排障)

---

## 1. SoloLakehouse 是什么

SoloLakehouse 是一个**可完整本地运行的 Lakehouse 参考实现**，用开源工具模拟 Databricks、Snowflake 等商业数据平台的核心分层架构。

**它不是一个框架，也不是一个库**——它是一个你可以克隆、跑通、读懂并修改的真实工程仓库。

### 平台包含什么

| 层 | 组件 | 作用 |
|----|------|------|
| 对象存储 | MinIO | S3 兼容存储，保存所有 Parquet 数据 |
| 元数据 | Hive Metastore + PostgreSQL | 表注册与 SQL 可寻址 |
| 查询引擎 | Trino | 跨层 SQL 查询 |
| ML 跟踪 | MLflow | 实验参数、指标、模型记录 |
| 编排 | Dagster | 资产化 pipeline 调度与治理（v2） |

### 数据链路

```
ECB API（欧央行利率）
DAX CSV（德国股市日线）
        ↓
   Bronze 层（原始 Parquet，不可变）
        ↓
   Silver 层（清洗、派生字段、去重）
        ↓
   Gold 层（ECB 事件研究特征表）
        ↓
   MLflow（XGBoost / LightGBM 实验）
```

### 版本状态

| 版本 | 状态 | 核心能力 |
|------|------|---------|
| **v1.0** | ✅ 已交付 | 五服务平台基线，端到端线性 pipeline |
| **v2.0** | ✅ 当前版本 | Dagster 资产编排，调度 / 传感器 / 资产检查 |
| **v3.0** | 📋 规划中 | Kubernetes、Terraform、Secrets 治理、SLO 可观测性 |

---

## 2. 环境准备

### 2.1 硬件要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核以上 |
| 可用内存 | 4 GB | 8 GB 以上 |
| 磁盘空间 | 5 GB | 10 GB 以上 |
| 网络 | 需要（拉取镜像 + ECB API） | — |

> v2 运行 8 个容器，空载内存占用通常在 2–3 GB。

### 2.2 软件要求

| 软件 | 版本要求 | 安装验证 |
|------|---------|---------|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | v2.20+（插件形式） | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| make | 任意版本 | `make --version` |

### 2.3 操作系统

| 系统 | 支持情况 |
|------|---------|
| Linux（Ubuntu 22.04+ / Debian 12+） | ✅ 推荐 |
| macOS 13+（Docker Desktop） | ✅ 支持 |
| Windows 11 + WSL2 | ✅ 在 WSL 终端内运行所有命令 |

---

## 3. 安装与启动

### 3.1 从 GitHub 克隆

```bash
git clone https://github.com/<your-username>/SoloLakehouse.git
cd SoloLakehouse
```

### 3.2 配置环境变量

```bash
cp .env.example .env
```

`.env` 包含所有服务的默认本地开发凭据（端口、密码等）。**本地体验无需修改**，如有端口冲突再编辑对应变量。

### 3.3 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# Windows WSL 同上
pip install -r requirements.txt
```

### 3.4 启动平台

**推荐：首次运行使用 `make setup`**（自动检查 Docker、补 `.env`、拉取镜像、启动并等待就绪）

```bash
make setup
```

或直接启动（已有镜像时更快）：

```bash
make up
```

`make up` 会等待所有服务通过健康检查，完成后输出：

```
SoloLakehouse is ready.
  MinIO Console:  http://localhost:9001
  Trino UI:       http://localhost:8080
  MLflow UI:      http://localhost:5000
  Dagster UI:     http://localhost:3000
```

> 首次启动需要拉取镜像，约 5–10 分钟。后续启动通常 1–2 分钟。

---

## 4. 验证平台就绪

```bash
make verify
```

全部通过时输出如下：

```
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS    Buckets: sololakehouse, mlflow-artifacts
PostgreSQL       PASS    Databases: hive_metastore, mlflow
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200
Dagster          PASS    HTTP 200 /server_info
```

任何服务显示 `FAIL` 或 `TIMEOUT`，请参考[第 10 节排障指南](#10-常见问题与排障)。

---

## 5. v1 体验：线性脚本管道

v1 是项目的基础路径——一个结构清晰、六步顺序执行的数据工程管道，不依赖外部编排服务。

### 5.1 运行 v1 管道

```bash
make pipeline-v1
```

或等价命令：

```bash
make pipeline PIPELINE_MODE=v1
```

### 5.2 执行过程

管道按以下六个步骤顺序运行：

| 步骤 | 名称 | 内容 |
|------|------|------|
| 1 | ECB Ingestion | 从 ECB SDW REST API 采集欧央行利率数据，Pydantic 校验后写入 Bronze 层 |
| 2 | DAX Ingestion | 读取 `data/sample/dax_daily_sample.csv`，校验后写入 Bronze 层 |
| 3 | ECB Bronze → Silver | 类型修正、填充、派生 `rate_change_bps` 字段 |
| 4 | DAX Bronze → Silver | 过滤周末、派生 `daily_return` |
| 5 | Silver → Gold | 以 ECB 利率决议日为锚点，拼接 DAX 前后 5 日行情，构建事件研究特征表 |
| 6 | ML Experiment | XGBoost / LightGBM 超参组合实验，结果写入 MLflow |

成功时输出类似：

```
[Step 1/6] ECB Ingestion ✓  (valid=847, rejected=0)
[Step 2/6] DAX Ingestion ✓  (valid=1305, rejected=0)
[Step 3/6] ECB Bronze → Silver ✓
[Step 4/6] DAX Bronze → Silver ✓
[Step 5/6] Silver → Gold ✓
[Step 6/6] ML Experiment ✓  best_run_id=<mlflow-run-id>
```

### 5.3 查看管道产出

**MinIO — 查看分层数据文件**

打开 http://localhost:9001（用 `.env` 中的 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`，默认均为 `sololakehouse` / `sololakehouse123`），浏览器端浏览：

```
sololakehouse/
  bronze/
    ecb_rates/ingestion_date=YYYY-MM-DD/
    dax_daily/ingestion_date=YYYY-MM-DD/
    rejected/source=ECB/ingestion_date=YYYY-MM-DD/
  silver/
    ecb_rates_cleaned/
    dax_daily_cleaned/
  gold/
    ecb_dax_features/
```

**Trino — SQL 查询 Gold 层**

```bash
docker exec -it slh-trino trino
```

进入 Trino CLI 后执行：

```sql
-- 查看可用 catalog 和 schema
SHOW CATALOGS;
SHOW SCHEMAS IN hive;

-- 查询 Gold 特征表
SELECT
    ecb_date,
    rate_change_bps,
    dax_return_pre_5d,
    dax_return_post_5d
FROM hive.gold.ecb_dax_features
ORDER BY ecb_date
LIMIT 10;
```

退出 CLI：`quit`

**MLflow — 查看 ML 实验**

打开 http://localhost:5000，进入实验 `ecb_dax_impact`，可以看到：
- 每次运行的模型类型（xgboost / lightgbm）和超参数
- 验证集 RMSE / MAE 指标
- 最优模型的 run_id

### 5.4 v1 的工程特性

v1 在脚本层面已经具备生产化思维：

- **增量采集**：检测今日分区是否已存在，避免重复写入
- **强制重跑**：`make pipeline ARGS="--force"` 绕过增量检查
- **采集重试**：ECB API 自动重试 3 次，失败时抛出 `CollectorUnavailableError`
- **Rejected records**：Pydantic 校验失败的记录单独落盘到 `bronze/rejected/`，不丢失
- **质量检查**：Bronze 层检查未来日期、日期连续性、schema 完整性

---

## 6. v2 体验：Dagster 资产编排

v2 在 v1 的数据逻辑之上增加了**平台语义**：数据不再是"脚本的副产物"，而是明确的、可治理的**软件定义资产（SDA）**。

### 6.1 运行 v2 管道

```bash
make pipeline
```

这是 v2 的默认路径，等价于在 Dagster 容器内执行 `full_pipeline_job`。

成功时输出 Dagster 执行日志，最后一行包含：

```
RUN_SUCCESS
```

### 6.2 资产依赖图

v2 定义了 6 个软件定义资产，形成明确的依赖关系：

```
ecb_bronze ──────┐
                 ├──► ecb_silver ──┐
                 │                 ├──► gold_features ──► ml_experiment
dax_bronze ──────┘                 │
                 ├──► dax_silver ──┘
```

每个资产在 Dagster UI 里可以：
- 查看执行历史与输出元数据（行数、路径、耗时）
- 单独重新物化（不必重跑整条链路）
- 查看上下游依赖关系

### 6.3 Dagster UI 操作指南

打开 http://localhost:3000

**Asset Graph（资产图）**

主页面 → 点击 **Assets** → 选择 **Asset Graph**

可以看到 6 个资产节点及其依赖连线。点击任意资产节点查看：
- 最近物化时间和状态
- 输出元数据（行数、路径等）
- 上下游依赖

**手动触发全链路运行**

1. 点击右上角 **Materialize all**
2. 在弹出确认框点击 **Materialize**
3. 跳转至 Runs 页面观察执行进度

**查看运行日志**

Runs 页面 → 点击任意一次运行 → 展开各步骤查看结构化日志（structlog 格式）

**单资产重新物化**

适用场景：某步骤失败或数据更新后只需刷新特定层。

1. 点击目标资产（如 `gold_features`）
2. 右侧面板点击 **Materialize**
3. Dagster 自动检查依赖，仅运行必要的上游资产

### 6.4 调度与自动化

**每日自动调度**

导航到 **Deployments → Schedules**，找到 `daily_pipeline_schedule`：
- Cron：`0 6 * * 1-5`（工作日 UTC 06:00）
- 状态默认关闭；点击 **Running** 开关启用

**数据新鲜度传感器**

导航到 **Deployments → Sensors**，找到 `ecb_data_freshness_sensor`：
- 每 30 分钟检查一次 ECB Bronze 分区时间
- 若最新分区超过 48 小时未更新，自动触发 `ecb_bronze` 重新采集

**Gold 层资产检查**

导航到 **Asset Checks**，找到 `gold_features_min_rows_check`：
- 每次 `gold_features` 物化后自动运行
- 检查 Gold 层行数 ≥ 10（少于此值表示上游数据可能异常）

### 6.5 v1 与 v2 路径对比

| 维度 | v1（legacy script） | v2（Dagster） |
|------|---------------------|---------------|
| 触发方式 | `make pipeline-v1` | `make pipeline` |
| 执行视角 | 线性步骤日志 | 资产依赖图 + 可视化 |
| 失败恢复 | 从头重跑或手动跳步 | 单资产重新物化 |
| 调度 | 无 | 每日 cron + 传感器 |
| 数据质量检查 | 脚本日志 | Asset Check（有状态、可追溯） |
| 适用场景 | 快速本地验证、回退路径 | 日常运营、演示平台治理能力 |

两条路径**数据逻辑完全一致**，产出的 Bronze / Silver / Gold 数据相同。v1 作为 v2 的回退路径长期保留。

---

## 7. 探索平台 UI

### 7.1 MinIO Console

**地址**：http://localhost:9001
**登录**：用 `.env` 中的 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`（默认 `sololakehouse` / `sololakehouse123`）

功能：
- 浏览 Bronze / Silver / Gold Parquet 文件
- 下载单个 Parquet 文件到本地查看
- 查看 `mlflow-artifacts` bucket（MLflow 模型文件）
- 查看 `bronze/rejected/` 路径下的拒绝记录

### 7.2 Trino UI + CLI

**Web UI**：http://localhost:8080（只读，显示查询历史和集群状态）

**CLI 进入方式**：

```bash
docker exec -it slh-trino trino
```

常用 SQL：

```sql
-- 查看所有 schema
SHOW SCHEMAS IN hive;

-- 查看 Gold 表结构
DESCRIBE hive.gold.ecb_dax_features;

-- ECB 事件研究：利率上调后 DAX 的反应
SELECT
    ecb_date,
    rate_change_bps,
    ROUND(dax_return_post_5d * 100, 2) AS dax_5d_return_pct
FROM hive.gold.ecb_dax_features
WHERE rate_change_bps > 0
ORDER BY ecb_date;

-- Silver 层查看清洗后的 ECB 利率
SELECT * FROM hive.silver.ecb_rates_cleaned LIMIT 5;
```

### 7.3 MLflow UI

**地址**：http://localhost:5000

导航路径：
1. 左侧栏点击实验 **ecb_dax_impact**
2. 看到所有运行记录，按 `val_rmse` 升序排序找最佳模型
3. 点击任意 Run 查看：
   - **Parameters**：`n_estimators`、`max_depth`、`learning_rate`、模型类型
   - **Metrics**：`val_rmse`、`val_mae`、训练时长
   - **Artifacts**：模型文件（存储在 MinIO `mlflow-artifacts` bucket）

### 7.4 Dagster UI

**地址**：http://localhost:3000

页面导航：

| 页面 | 路径 | 主要用途 |
|------|------|---------|
| Asset Graph | Assets → Asset Graph | 查看资产依赖图 |
| Runs | Runs | 查看执行历史、日志、耗时 |
| Schedules | Deployments → Schedules | 管理定时调度 |
| Sensors | Deployments → Sensors | 管理数据新鲜度传感器 |
| Asset Checks | Assets → Asset Checks | 查看数据质量检查结果 |

---

## 8. 完整命令速查

### 平台生命周期

```bash
make setup          # 首次运行推荐：检查 Docker → 补 .env → 拉镜像 → 启动 → 等待就绪
make up             # 启动所有服务（已有镜像时直接用）
make verify         # 检查 6 个服务健康状态
make down           # 停止服务（数据保留在 volumes）
make clean          # 停止服务并删除所有 volumes（破坏性）
```

### Pipeline 执行

```bash
make pipeline                        # v2 默认：Dagster full_pipeline_job
make pipeline-v1                     # v1 legacy：线性脚本
make pipeline PIPELINE_MODE=v1       # 同上
make pipeline ARGS="--force"         # v1 路径强制重跑（忽略增量检查）
make pipeline PIPELINE_MODE=v2 DAGSTER_JOB=full_pipeline_job  # 显式指定 job
```

### 开发工具

```bash
make test           # 运行所有单元测试（无需 Docker）
make test-cov       # 带覆盖率报告
make lint           # ruff 代码检查
make typecheck      # mypy 类型检查
make dagster-ui     # 浏览器打开 Dagster UI（:3000）
```

### Trino 快速访问

```bash
docker exec -it slh-trino trino      # 进入 Trino CLI
```

---

## 9. v3 规划预览

v2 解决了"如何运营这个平台"，v3 的目标是"如何让这个平台具备生产级部署能力"。

### 核心方向

| 方向 | 内容 |
|------|------|
| **基础设施** | Kubernetes + Helm + Terraform 替代 Docker Compose 成为部署基座 |
| **多环境管理** | `dev → staging → production` 环境晋级链路，含 rollback 标准 |
| **安全治理** | Secrets lifecycle（替代静态 `.env`），least-privilege 访问模型，审计日志 |
| **可观测性** | SLO 定义 + metrics 采集 + 告警规则 + Dashboard + 事故 runbook |
| **数据治理** | Gold 层和关键 Silver 层的治理契约（data_owner、refresh_sla、quality_class） |
| **ML 实验治理** | 可复现的训练评估合约，artifact lineage，跨环境实验一致性 |

### 明确不在 v3 范围内的组件

以下组件在 v3 被显式排除，避免过早引入复杂度：

- Kafka / Flink（流处理）
- OpenMetadata / DataHub（统一数据目录）
- Delta Lake / Iceberg（表格式替换）
- 在线模型服务（Online Serving）
- Keycloak 级别的终端用户身份系统
- Superset / FastAPI

这些组件将在有明确业务场景驱动时，以 scenario-driven 方式引入，而不是为了"看起来完整"。

### 当前定位

v2 平台适合：小型内部数据团队、MVP 级数据平台、中低规模批处理工作流。

v3 完成后适合：具备合规要求的数据平台、需要 HA 和多环境管理的团队、接近生产级的内部平台。

---

## 10. 常见问题与排障

### Q1：`make verify` 某个服务 FAIL / TIMEOUT

**hive-metastore FAIL**
原因：PostgreSQL 尚未完全就绪时 Hive Metastore 启动失败。
解决：
```bash
make clean && make up
```

**Trino FAIL — "catalog not available"**
原因：Hive Metastore 仍在初始化中。
解决：等待 60 秒后重新执行 `make verify`。

**Dagster FAIL**
原因：Dagster webserver 启动较慢，`start_period` 为 60 秒。
解决：等待 90 秒后重新执行 `make verify`。如果持续失败：
```bash
docker logs slh-dagster-webserver --tail 50
```

**MLflow FAIL**
原因：通常是 PostgreSQL 连接问题。
解决：`make clean && make up`

---

### Q2：`make pipeline` 报错 "Error: No such container: slh-dagster-webserver"

原因：Dagster 容器未在运行。
解决：
```bash
make up           # 重新启动所有服务
make verify       # 确认 Dagster 状态为 PASS 后再跑 pipeline
```

---

### Q3：ECB API 超时

原因：ECB SDW API 有时响应慢或限流。
解决：
```bash
make pipeline     # 直接重跑，内置自动重试
```

如果多次超时，切换到 v1 路径调试：
```bash
make pipeline-v1
```

---

### Q4：`make pipeline-v1` 跑过了但 Trino 查 Gold 表没数据

原因：v1 路径会注册 Trino 表，但需要 Trino 已完全就绪。
解决：
```bash
make verify        # 确认 Trino 状态 PASS
make pipeline-v1   # 重新跑
```

---

### Q5：重启后数据丢失

原因：使用了 `make clean`（会删除所有 Docker volumes）。
正确停止方式（保留数据）：
```bash
make down          # 保留 volumes
make up            # 重启后数据自动恢复
```

---

### Q6：MinIO "bucket already exists" 错误

原因：`minio-init` 容器重复执行了 bucket 创建。
处理：**可以忽略**。`minio-init` 是幂等的，不影响数据。

---

### Q7：端口冲突

如果 9000、9001、8080、5000、3000、5432 中有端口已被占用，在 `.env` 中修改对应端口变量：

```bash
MINIO_API_PORT=9010
MINIO_CONSOLE_PORT=9011
PG_PORT=5433
```

修改后重新启动：
```bash
make down && make up
```

---

### 查看容器日志

```bash
docker logs slh-minio --tail 30
docker logs slh-postgres --tail 30
docker logs slh-hive-metastore --tail 30
docker logs slh-trino --tail 30
docker logs slh-mlflow --tail 30
docker logs slh-dagster-webserver --tail 30
docker logs slh-dagster-daemon --tail 30
```

---

## 附录：服务端口一览

| 服务 | 端口 | 访问方式 |
|------|------|---------|
| MinIO API | 9000 | S3 SDK / CLI |
| MinIO Console | 9001 | 浏览器 |
| PostgreSQL | 5432 | psql / 数据库客户端 |
| Hive Metastore | 9083 | Thrift（内部） |
| Trino | 8080 | 浏览器 / CLI |
| MLflow | 5000 | 浏览器 |
| Dagster UI | 3000 | 浏览器 |
