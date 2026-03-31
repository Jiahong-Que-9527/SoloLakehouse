# SoloLakehouse 深度部署与运行全解（面向使用者）

> 本文面向希望**透彻理解**本仓库如何在本机或开发环境中**部署、启动、验证与运行数据管道**的读者。内容覆盖架构心智模型、Docker Compose 各服务职责、环境变量契约、Medallion 数据流、默认的 Dagster 编排路径与兼容的 Legacy 脚本路径、Trino/Hive/Iceberg 注册逻辑、MLflow 与可选组件，以及故障排查思路。  
> 本文档为独立长文，可与 `docs/deployment.md`、`docs/quickstart.md`、`docs/architecture.md`、`docs/USER_GUIDE.md` 交叉阅读。

---

## 一、本文档的定位与阅读建议

SoloLakehouse 在仓库根目录的 `README.md` 与 `CLAUDE.md` 中已经给出了高度浓缩的定位：**它不是可复用的框架库，而是一个用开源组件搭起来的 Lakehouse 参考实现**，演示对象存储、Medallion 转换、SQL 查询与 ML 实验跟踪如何组合成类似 Databricks、Snowflake 一类平台的“纵向切片”。若你把自己定位为“使用者”——需要在本机跑通、改参数、接自己的数据源或向团队讲解——仅有 Quick Start 往往不够，因为**部署与运行**牵涉：

- 多个长期运行的容器及其**依赖顺序**与**健康检查**；
- 宿主机 Python 虚拟环境与容器内 Dagster 镜像的**两套运行时**（`make pipeline` 在容器内执行 Dagster Job，而 `make verify` 与 Legacy 管道多在宿主机用 `.venv`）；
- MinIO（S3 语义）、PostgreSQL（多业务库）、Hive Metastore（表元数据）、Trino（联邦 SQL）、MLflow、Dagster 之间的**数据面与控制面**分工；
- Gold 层**先写 Parquet、再通过 Trino 注册 Hive 外表并 CTAS 到 Iceberg** 这一“双阶段暴露”模式。

阅读本文时，建议你在本地已克隆仓库并至少执行过一次 `make setup` 或 `make up`，这样每个名词（容器名、端口、库名）都能对应到真实进程。若你尚未安装 Docker，请先完成 `docs/deployment.md` 中的软件前置章节，再回到本文理解“为什么需要这些组件”。

---

## 二、项目在“平台地图”上的位置

从数据工程视角，一个最小可演示的 Lakehouse 通常包含：

1. **对象存储**：存放不可变或版本化的数据集文件（此处为 MinIO，兼容 S3 API）。
2. **表格式与目录**：让 SQL 引擎能把“文件夹里的 Parquet”当成表（Hive 外部表 + Metastore；Gold 另用 Iceberg 表增强演示）。
3. **查询引擎**：对多数据源执行 ANSI SQL（Trino，带 `hive` 与 `iceberg` 两个 catalog）。
4. **编排（可选但本仓库已默认）**：把采集、转换、注册、训练步骤变成可重试、可定时、可观测的作业（Dagster）。
5. **ML 实验跟踪**：记录参数、指标与模型产物（MLflow，后端 PostgreSQL + artifact 在 MinIO）。

SoloLakehouse **刻意**使用 Docker Compose 单节点而非 Kubernetes（见 ADR-001），以降低读者心智负担；同时选用 Trino 而非嵌入式 DuckDB（ADR-002），以强调**联邦查询 + Hive Metastore** 这一企业湖仓常见组合。理解这一点，你就不会问“为什么不用一个 SQLite 解决所有问题”——本仓库的教学目标包含**组件边界**与**集成方式**，而非最小代码量。

---

## 三、版本叙事：v1、v2、v2.5 与 v3 方向

官方路线图以“可交付版本”组织目标（详见 `docs/roadmap.md`）。对使用者而言，只需掌握以下叙事：

- **v1（已交付）**：五条核心服务（MinIO、PostgreSQL、Hive Metastore、Trino、MLflow）+ 可跑通的端到端管道 + 健康检查与文档。证明“湖仓闭环能转起来”。
- **v2（当前默认）**：在 v1 之上增加 **Dagster**（`dagster-webserver` 与 `dagster-daemon`），用 **软件定义资产（Software-Defined Assets）** 表达 Bronze/Silver/Gold/ML 的依赖图，并提供调度、传感器与资产检查；同时保留 **Legacy 线性脚本** `scripts/run-pipeline.py` 作为兼容路径（`make pipeline PIPELINE_MODE=v1` 等）。
- **v2.5（参考扩展）**：Gold 在 Trino 中除 Hive 外表外，还通过 **Iceberg** catalog 暴露 `iceberg.gold.ecb_dax_features_iceberg`；可选 **OpenMetadata**、**Superset** 通过额外 Compose 文件与 profile 启动。
- **v3（规划中）**：生产化与治理强化（多环境晋升、密钥与访问治理、SLO 与告警、K8s/Helm/Terraform 等），**不改变**你阅读本文所涉及的“本机参考部署”主线，但会改变运维语义。

因此：**你日常使用的“默认路径”是 v2 的 Dagster**；**你向他人解释“最小可运行核心”时可以从 v1 五服务讲起**，再叠加编排层。

---

## 四、技术栈总览与职责分工

下表将“组件—职责—默认端口”对齐，便于与 `docker/docker-compose.yml` 对照。

| 组件 | 职责 | 宿主机端口（默认） |
|------|------|-------------------|
| MinIO | S3 兼容对象存储；Bronze/Silver/Gold Parquet、MLflow artifact | 9000 API，9001 控制台 |
| minio-init | 一次性桶初始化（`sololakehouse`、`mlflow-artifacts`） | 无对外端口 |
| PostgreSQL | 系统数据库：Hive Metastore、MLflow、Dagster 实例存储等 | 5432 |
| Hive Metastore | Thrift 元数据服务；Trino 的 Hive/Iceberg 目录依赖其表定义与位置 | 9083 |
| Trino | 分布式 SQL；`hive` 与 `iceberg` catalog | 8080 |
| MLflow | Tracking Server；实验与模型元数据在 PG，大文件在 MinIO | 5000 |
| dagster-webserver | Dagster UI 与 Job 执行入口 | 3000 |
| dagster-daemon | 调度器、传感器、运行启动 | 无对外端口（内部） |

**数据路径简述**：采集与转换代码把 Parquet 写入 MinIO；Trino 通过 Metastore 知道“表在哪里”；Gold 注册步骤用 Trino REST API 执行 DDL/CTAS；ML 训练代码读 Gold（可直接读 Parquet 或通过 Trino 读 Iceberg，视 `ml/` 实现而定）并把结果记入 MLflow。

---

## 五、仓库目录与心智模型

根目录中与“部署运行”强相关的路径包括：

- **`docker/`**：`docker-compose.yml`（核心栈）、`docker-compose.openmetadata.yml`、`docker-compose.superset.yml`（可选叠加）、各服务 Dockerfile（如 `docker/dagster/Dockerfile`、`docker/hive-metastore`、`docker/mlflow`）。
- **`config/`**：Trino `config.properties`、catalog **模板**目录（注意是模板，见下文 `trino-entrypoint.sh`）、PostgreSQL `init.sql`（首次初始化建库）。
- **`scripts/`**：`bootstrap-postgres.py`（确保库存在）、`verify-setup.py`（健康检查）、`init-minio.sh`（桶）、`trino-entrypoint.sh`（展开 catalog 模板）、`run-pipeline.py`（Legacy 管道）。
- **`dagster/`**：`definitions.py`（作业、调度、传感器注册）、`assets.py`（资产实现）、`resources.py`（MinIO/管道配置）、`dagster.yaml`（Dagster 使用 PostgreSQL 存储实例数据）、`workspace.yaml`（加载 `definitions.defs`）。
- **`ingestion/`、`transformations/`、`ml/`**：业务逻辑主体；Dagster 资产直接调用这些模块。

把 **`make`** 当作**面向使用者的命令门面**：它封装了 compose 调用、数据库引导、等待健康、以及管道执行入口，减少你记忆冗长 docker 命令的负担。

---

## 六、运行前准备：硬件、软件、操作系统

`docs/deployment.md` 给出的建议可概括为：x86_64/ARM 上现代 Docker，**至少约 4GB 可用内存**与数 GB 磁盘；推荐 8GB+ 内存以便 Trino、Metastore、Dagster 同时空闲占用时仍有余量。可选栈（OpenMetadata、Elasticsearch）显著增加内存压力，应按需启动。

软件层面需要：

- Docker Engine 与 **Compose V2 插件**（`docker compose` 子命令）；
- **Python 3.13+**（与项目依赖一致）；
- `make`。

操作系统上 Linux 最省心；macOS 用 Docker Desktop；Windows 建议 WSL2 并在 Linux 发行版内执行文档命令，以避免路径与换行差异。

---

## 七、环境变量与 `.env`：一台机器上的“合同”

仓库提供 `.env.example`，`make setup` 会在缺少 `.env` 时复制它。核心变量包括：

- **MinIO 凭证**：`MINIO_ROOT_USER`、`MINIO_ROOT_PASSWORD`；同时 **S3 兼容客户端**使用 `S3_ACCESS_KEY`、`S3_SECRET_KEY`（可与 MinIO 用户一致）。
- **端点**：宿主机侧常用 `MINIO_ENDPOINT=localhost:9000`；**容器内**服务互连用 `minio:9000`（Compose 服务名）。
- **PostgreSQL**：`POSTGRES_USER`、`POSTGRES_PASSWORD`；以及可选的 `POSTGRES_HOST`/`POSTGRES_PORT`（验证脚本连宿主机端口）。
- **MLflow**：`MLFLOW_S3_ENDPOINT_URL` 指向 MinIO；`MLFLOW_TRACKING_URI` 在宿主机跑脚本时常为 `http://localhost:5000`。
- **Trino（可选）**：若在宿主机运行需要访问 Trino 的代码，可设 `TRINO_URL=http://localhost:8080`。

`.env` 被多个路径加载：`scripts/bootstrap-postgres.py`、`scripts/verify-setup.py`、`scripts/run-pipeline.py` 等均实现了“若键未在环境中则读 `.env`”的轻量解析。**注意**：Dagster 容器内的环境由 `docker-compose.yml` 的 `environment` 显式注入，修改 `.env` 后通常需要 **`docker compose up -d` 重建/重载相关服务** 才能在容器内生效。

---

## 八、一键部署链路：`make setup` 与 `make up` 拆解

### 8.1 `make setup`

`Makefile` 中 `setup` 目标做四件事：

1. 检查 Docker daemon 可用；
2. 若无 `.env` 则从 `.env.example` 复制；
3. `docker compose pull` 拉取镜像；
4. 调用 `make up`。

适合**第一次**克隆仓库后的“从零到就绪”。

### 8.2 `make up`

`make up` 等价于：

1. `docker compose -f docker/docker-compose.yml up -d` —— 后台启动所有定义的服务；
2. `make bootstrap-db` —— 运行 `scripts/bootstrap-postgres.py`，确保 PostgreSQL 中存在 `hive_metastore`、`mlflow`、`dagster_storage`（及通过 `EXTRA_POSTGRES_DATABASES` 附加的库，例如 Superset 元数据）；
3. `make wait` —— 在最长约 5 分钟内轮询 `scripts/verify-setup.py`，直到全部检查通过。

**为什么需要 bootstrap**：`config/postgres/init.sql` 只在 **Postgres 数据目录首次初始化**时执行；若你使用持久卷且曾经初始化过旧库，或从其他环境恢复数据，init.sql 不会再次运行。bootstrap 脚本弥补“库可能缺失”的情况，使 `make up` 幂等性更好。

### 8.3 `make wait` 的意义

冷启动时 Hive Metastore 与 Trino 可能需要数十秒到一两分钟；Dagster Webserver 也要等代码位置加载完毕。`make wait` 用**真实探测**（与 `make verify` 同源脚本）而非固定 `sleep`，避免用户过早执行 `make pipeline` 导致失败。

---

## 九、Docker Compose 中的每一个服务（核心栈）

以下按 `docker/docker-compose.yml` 叙述（服务名与容器名见文件）。

### 9.1 MinIO

镜像固定为项目所选版本。启动命令 `server /data --console-address ":9001"`，数据在命名卷 `minio_data`。健康检查请求 `http://localhost:9000/minio/health/live`。

**使用者要点**：所有“湖”中的 Parquet 最终都落在此；Trino 的 S3 路径形如 `s3://sololakehouse/gold/...`。

### 9.2 minio-init

依赖 MinIO healthy 后运行 `scripts/init-minio.sh`：用 `mc` 配置 alias 并 `mc mb --ignore-existing` 创建 `sololakehouse` 与 `mlflow-artifacts`。`restart: "no"` 表示一次性任务。

### 9.3 PostgreSQL

镜像 `postgres:17`，持久卷 `postgres_data`，挂载 `config/postgres/init.sql` 到 `docker-entrypoint-initdb.d`。对外暴露 5432。

**三库语义**：

- `hive_metastore`：Hive Metastore 的 JDBC 目标；
- `mlflow`：MLflow backend store；
- `dagster_storage`：Dagster 实例、运行历史等（见 `dagster/dagster.yaml`）。

### 9.4 Hive Metastore

自定义构建 `docker/hive-metastore`，依赖 Postgres 与 MinIO healthy。环境变量注入 Metastore 连接 DB 与 S3 端点/密钥。端口 9083，健康检查通过 `nc` 探测 Thrift 端口。

**使用者要点**：没有它，Trino 的 Hive 目录无法持久化表定义；Iceberg 在本项目中也与 Hive Metastore 协同（Iceberg catalog 配置指向同一 Metastore）。

### 9.5 Trino

官方镜像 `trinodb/trino:480`。`user: "0"` 与自定义 entrypoint 是为了在启动前把 **catalog 模板**渲染到可写目录。挂载：

- `config/trino/config.properties` → `/etc/trino/config.properties`；
- `config/trino/catalog` → `/etc/trino/catalog-template`（只读模板）；
- `scripts/trino-entrypoint.sh` → 入口脚本。

健康检查访问 `http://localhost:8080/v1/info`。

### 9.6 MLflow

自定义构建 `docker/mlflow`，依赖 Postgres 与 MinIO。环境变量将 artifact store 指向 MinIO（通过 `MLFLOW_S3_ENDPOINT_URL` 与 AWS 兼容密钥）。端口 5000，`/health` 检查。

### 9.7 dagster-webserver 与 dagster-daemon

二者共用 **`docker/dagster/Dockerfile`** 构建的镜像：在镜像内安装 `requirements.txt` + `requirements-dagster.txt`，复制 `ingestion/`、`transformations/`、`ml/`、`scripts/`、`dagster/` 到 `/app`，`PYTHONPATH=/app`。

- **Webserver**：命令 `dagster-webserver -h 0.0.0.0 -p 3000 -w /app/dagster/workspace.yaml`，对外 3000。环境变量注入 MinIO 端点、S3 密钥、`MLFLOW_TRACKING_URI`、`TRINO_URL`、`POSTGRES_*`、`DAGSTER_HOME` 等。
- **Daemon**：`dagster-daemon run -w ...`，依赖 webserver healthy；负责调度与传感器。

二者共享命名卷 `dagster_storage` 挂载到 `/app/dagster/storage`，与 `dagster.yaml` 中 PostgreSQL 存储共同构成 Dagster 的持久化状态。

**关键结论**：你在宿主机 `pip install` 的包**不会**自动进入该镜像；修改 Python 业务代码后需要 **重建镜像**（`docker compose build`）或采用开发挂载策略（本仓库默认生产型镜像路径，以参考实现为主）。

---

## 十、启动顺序、健康检查与依赖

Compose 的 `depends_on` + `condition: service_healthy` 保证：

- MinIO、Postgres 先就绪；
- Hive Metastore 在 MinIO、Postgres 之后；
- Trino 在 Metastore、MinIO 之后；
- MLflow 在 Postgres、MinIO 之后；
- Dagster 服务在 Postgres、MinIO 之后；daemon 还等待 webserver。

**仍建议**以 `make verify` 输出为准，因为应用层就绪（例如 Trino catalog 加载完毕）晚于 TCP 端口开放的情况偶尔存在。

---

## 十一、PostgreSQL 多库模型与 `bootstrap-postgres.py` 详解

`scripts/bootstrap-postgres.py` 维护“必需数据库列表”：

- 默认 `REQUIRED_DATABASES = ("hive_metastore", "mlflow", "dagster_storage")`；
- 若环境变量 `EXTRA_POSTGRES_DATABASES` 设为逗号分隔列表（`make up-superset` 会传入 `superset_metadata`），则一并创建。

实现上优先尝试 `docker exec slh-postgres psql`（当你在宿主机有 Docker CLI 且容器名一致时），失败则回退到 TCP 直连 `POSTGRES_HOST:POSTGRES_PORT`。

**对你意味着什么**：即使你从未读过 `init.sql`，只要 Postgres 在跑，`make up` 会尽量保证三个核心库存在，避免 Hive/MLflow/Dagster 各自报“database does not exist”。

---

## 十二、MinIO 与桶初始化

桶 `sololakehouse` 承载业务数据路径前缀 `bronze/`、`silver/`、`gold/`；`mlflow-artifacts` 专供 MLflow。`init-minio.sh` 使用 MinIO Client（`mc`）在 `minio` 服务地址上创建桶；重复执行时 `--ignore-existing` 避免失败。

若你清空卷后重跑，`make up` 会再次 init，这是正常路径。

---

## 十三、Trino 目录模板与 `trino-entrypoint.sh` 机制

`config/trino/catalog/` 下的 `*.properties` 文件常含 `${S3_ACCESS_KEY}` 等占位符。容器启动时 `scripts/trino-entrypoint.sh` 对每个模板文件：

1. 用 `eval` + `printf` 将环境变量展开；
2. 写入 `/etc/trino/catalog/`（可写路径）；
3. `exec` 官方 `run-trino`。

**安全与运维提示**：模板目录只读挂载，避免容器内误写回宿主机；密钥来自 Compose 注入的环境变量。修改 catalog 后需重启 Trino 容器。

---

## 十四、Medallion 数据流：从源到金层

### 14.1 Bronze

采集器（`ingestion/collectors/`）从 ECB SDW REST API 与示例 DAX CSV 读数据，经 Pydantic 校验后由 `BronzeWriter` 写入 MinIO。**分区**按 `ingestion_date=` 组织，附 `_ingestion_timestamp`、`_source` 等列，强调**不可变追加**而非原地更新。

### 14.2 Silver

`transformations/ecb_bronze_to_silver.py` 与 `dax_bronze_to_silver.py` 提供 **纯函数 + `run()` 编排** 模式：从 MinIO 读 Bronze Parquet，清洗、派生指标（如 `rate_change_bps`、`daily_return`），写回 Silver 路径。

### 14.3 Gold

`silver_to_gold_features.py` 将两侧 Silver 合并为事件研究特征表，输出例如 `gold/rate_impact_features/ecb_dax_features.parquet`。

### 14.4 在 Trino 中“注册”Gold

`ingestion/trino_sql.py` 中 `register_gold_tables_trino` 做两件事：

1. **`register_hive_gold_staging_parquet`**：在 `hive.gold` schema 下创建**外部表** `hive.gold.ecb_dax_features`，`external_location` 指向 MinIO 上 Gold Parquet 目录（S3 语义路径）。
2. **`refresh_iceberg_gold_from_hive`**：`DROP TABLE IF EXISTS iceberg.gold.ecb_dax_features_iceberg` 后 **`CREATE TABLE ... AS SELECT * FROM hive.gold.ecb_dax_features`**，从而在 **Iceberg catalog** 中物化一张 Iceberg 表，便于演示 Iceberg 与 Trino 集成（ADR-013）。

该流程带重试与可重试错误判断，缓解 Trino 刚就绪时的竞态。

---

## 十五、两条执行路径：Dagster（默认）与 Legacy 脚本

### 15.1 默认：`make pipeline`（v2）

`Makefile` 在 `PIPELINE_MODE` 非 `v1`/`legacy` 时执行：

```bash
docker compose -f docker/docker-compose.yml exec dagster-webserver \
  dagster job execute -f /app/dagster/definitions.py -j full_pipeline_job
```

即在 **dagster-webserver 容器内** 用 CLI 执行名为 `full_pipeline_job` 的 Job。该 Job 在 `dagster/definitions.py` 中定义为覆盖全部资产的 `define_asset_job`。

### 15.2 兼容：`make pipeline-v1` / `make pipeline-legacy`

此时执行 `python scripts/run-pipeline.py`，在**宿主机 Python** 环境中跑线性步骤（同样调用采集、转换、`register_gold_tables_trino`、ML 评估）。适合对比行为或在不重建 Dagster 镜像时调试业务代码（仍需本机依赖齐全）。

### 15.3 路径差异的实操含义

- 修改 `dagster/assets.py` 后：**v2 路径**需**重建 Dagster 镜像**才能在容器内生效；
- 修改 `ingestion/`、`transformations/`、`ml/` 后：同上（除非挂载源码的 dev 编排）；
- **验证集群健康**始终在宿主机用 `.venv` 跑 `verify-setup.py` 即可。

---

## 十六、Dagster 深度：资产、作业、调度、传感器、检查

### 16.1 资产图

`dagster/assets.py` 定义资产：

- `ecb_bronze`、`dax_bronze`：调用 `ECBCollector`、`DAXCollector`，带重试策略；
- `ecb_silver`、`dax_silver`：依赖对应 Bronze 输出，调用 `ecb_bronze_to_silver.run`、`dax_bronze_to_silver.run`；
- `gold_features`：依赖两路 Silver 路径，调用 `silver_to_gold_features.run` 后 **`register_gold_tables_trino`**；
- `ml_experiment`：依赖 `gold_features`，调用 `ml.evaluate.run_experiment_set`。

资产返回路径字符串或摘要 dict，并在 `context.add_output_metadata` 中写入行数、分区日期等，便于 UI 展示。

### 16.2 作业与调度

`full_pipeline_job` 选中上述全部资产。`daily_pipeline_schedule` 使用 cron `0 6 * * 1-5`（UTC 工作日 06:00）。实际是否运行取决于 **dagster-daemon** 是否启动（Compose 已包含）。

### 16.3 传感器

`ecb_data_freshness_sensor` 每 30 分钟（`minimum_interval_seconds=1800`）检查 MinIO 上 `bronze/ecb_rates/` 最新 `ingestion_date` 分区；若无分区或数据滞后超过约 48 小时，则对 **`ecb_bronze`** 发起 `RunRequest`，实现“滞后则补采”的演示逻辑。

### 16.4 资产检查

`gold_features_min_rows_check` 验证 Gold Parquet 行数至少为 10，失败则资产检查不通过，用于数据质量门槛演示。

### 16.5 资源（Resources）

`MinioResource` 从环境变量构造 MinIO 客户端；`PipelineConfigResource` 提供 `bucket`、`mlflow_tracking_uri`、`trino_url`。容器内这些变量已针对 Docker 网络预设（例如 `TRINO_URL=http://trino:8080`）。

---

## 十七、MLflow 与机器学习实验

MLflow Tracking Server 接收 `ml.evaluate` 等模块的日志。典型内容包括实验名、参数、指标、模型文件；artifact 存储于 MinIO 桶 `mlflow-artifacts`。**在运行管道前**，MLflow UI 可能为空；完成 `make pipeline` 后应出现演示实验（如 `ecb_dax_impact`，以代码为准）。

若 UI 无实验，优先排查：管道是否真正跑完、MLflow 是否 healthy、S3 凭证是否一致。

---

## 十八、可选组件：OpenMetadata 与 Superset

### 18.1 OpenMetadata

`make up-openmetadata` 使用组合文件 `docker/docker-compose.openmetadata.yml` 并 `--profile openmetadata`。引入 Elasticsearch、OpenMetadata 自身依赖等，启动时间与内存占用显著上升。用于演示**数据目录**与 Trino 元数据采集（具体配置见官方文档与 ADR-014）。

验证：`make verify-openmetadata`。

### 18.2 Superset

`make up-superset` 会先确保核心 `postgres` 起来，再 `bootstrap-db` 创建 `superset_metadata`，接着构建本地 Superset 镜像并启动 profile。默认在 UI 中预置 Trino 连接字符串（Iceberg Gold 与 Hive default），便于 SQL Lab 探索。

验证：`make verify-superset`。登录信息默认在文档中给出（以 `docs/deployment.md` 为准）。

---

## 十九、验证体系：`make verify` 与测试命令

`scripts/verify-setup.py` 检查：

- MinIO 健康与桶存在；
- PostgreSQL 与必需库；
- Hive Metastore 端口；
- Trino `/v1/info`；
- MLflow `/health`；
- Dagster `/server_info`。

`make test` 运行单元测试（mock I/O，无需 Docker）。`make test-integration` 需集成环境。`make release-check` 组合 verify + 单元 + 集成，适合发布前自检。

---

## 二十、停止、清理与数据持久化

- **`make down`**：停止 Compose 服务，**保留**命名卷，数据仍在磁盘。
- **`make clean`**：`down -v`，删除卷，**destructive**，相当于重置 MinIO、Postgres、Dagster 本地状态。

演示或开发中若出现“元数据与对象存储不一致”，常见修复是 clean 后重跑 `make up` 与管道。

---

## 二十一、常见故障与排障思路（系统化）

1. **Hive Metastore 起不来**：往往是 Postgres 未就绪或库不存在；尝试 `make clean && make up`，或单独检查 `bootstrap-postgres` 输出。
2. **Trino 报 catalog 不可用**：冷启动延迟；等待后重试 `make verify`。
3. **ECB API 超时**：外部网络或限流；重试 `make pipeline`，或换 Legacy 路径对比。
4. **Iceberg/Gold DDL 失败**：确认 Gold Parquet 已写入；确认 Trino 对 S3 的权限与 Metastore 一致。
5. **Dagster 代码未更新**：重建 `dagster-webserver` / `dagster-daemon` 镜像。
6. **OpenMetadata/Superset OOM**：减少并发组件或增大 Docker 内存。

更完整列表见 `docs/deployment.md#troubleshooting`。

---

## 二十二、网络视角：宿主机 vs 容器 DNS

在 **宿主机**运行的脚本使用 `localhost:9000`、`localhost:8080` 等。在 **容器内**，应使用服务名：`minio:9000`、`trino:8080`、`postgres:5432`。Dagster 容器环境已按后者配置。若你自行在宿主机跑 `run-pipeline.py`，需保证 `TRINO_URL` 等指向可达地址。

---

## 二十三、安全与默认凭证

本仓库为**本地参考**，`.env.example` 含弱口令；**切勿**直接用于公网或未隔离网络。v3 方向的密钥治理与最小权限见 ADR-009 等。

---

## 二十四、从“跑通”到“读懂代码”的建议路线

1. 阅读 `docs/architecture.md` 与 `docs/medallion-model.md` 建立分层概念；
2. 对照 `dagster/assets.py` 跟踪一次资产执行顺序；
3. 阅读 `ingestion/trino_sql.py` 理解 Hive + Iceberg 双注册；
4. 打开 `ml/evaluate.py` 了解实验如何落 MLflow；
5. 阅读 `tests/` 中对应纯函数测试，理解可测试边界。

---

## 二十五、命令速查表

| 目的 | 命令 |
|------|------|
| 首次完整 setup | `make setup` |
| 启动并等待健康 | `make up` |
| 健康检查 | `make verify` |
| 默认跑管道 | `make pipeline` |
| Legacy 管道 | `make pipeline-v1` 或 `make pipeline-legacy` |
| 单元测试 | `make test` |
| 停服务保留数据 | `make down` |
| 重置卷 | `make clean` |
| 可选 OpenMetadata | `make up-openmetadata` |
| 可选 Superset | `make up-superset` |

---

## 二十六、Legacy 管道 `run-pipeline.py` 逐步语义（与 Dagster 对照）

`scripts/run-pipeline.py` 是 v1 风格的**线性编排器**：按固定顺序执行采集、转换、Gold 与 Trino 注册、ML 实验。与 Dagster 的差异不在于“业务逻辑函数”（二者都调用相同的 `ECBCollector`、`ecb_bronze_to_silver.run`、`silver_to_gold_features.run`、`register_gold_tables_trino`、`evaluate.run_experiment_set`），而在于：

- **编排外壳**：Legacy 用 Python 函数顺序 + 自定义 `StepError` / `retry_step`；Dagster 用资产依赖图 + 平台级重试、运行历史与 UI。
- **运行位置**：Legacy 默认在**宿主机**解释器执行，直接读取你 shell 中的 `MINIO_ENDPOINT` 等；Dagster 在**容器内**执行，环境由 Compose 注入。

脚本开头的 `load_dotenv_if_present()` 会在未导出变量时从项目根 `.env` 填充 `os.environ`，这对本地开发友好。`minio_base_url()` 将 `MINIO_ENDPOINT` 规范为带 `http://` 前缀的 URL，供 MinIO 客户端构造使用。`run_gold_and_register` 将 Silver→Gold 的 `run()` 与 Trino 注册捆绑，保证 **先落盘 Parquet、再执行 DDL**，与 Dagster 中 `gold_features` 资产一致。

当你需要**快速验证**“仅改了一个 transform 函数”时，在宿主机运行 `make pipeline-legacy` 往往迭代更快；当你需要验证**调度、传感器、资产检查、运行重放**等平台能力时，应使用默认的 `make pipeline` 并在 `http://localhost:3000` 观察。

---

## 二十七、一次“从冷启动到可查询”的推荐会话流程

下面按时间顺序描述一名使用者如何建立可重复的心智模型（命令以仓库根目录为准）：

1. **准备**：`python3 -m venv .venv && source .venv/bin/activate`，`pip install -r requirements.txt`。
2. **环境文件**：`cp .env.example .env`；若端口冲突，按 `docs/deployment.md` 调整并同步到 Compose（必要时自定义 `ports` 映射）。
3. **启动**：`make up`。观察 `bootstrap-postgres` 是否打印创建库信息；观察 `make wait` 是否在超时前结束。
4. **验证**：`make verify`，确认 MinIO 桶、Postgres 三库、Metastore、Trino、MLflow、Dagster 均为 PASS。
5. **跑管道**：`make pipeline`。首次拉 ECB 可能受网络影响，失败时重试即可。
6. **对象存储确认**：浏览器打开 MinIO 控制台，在 `sololakehouse` 桶中浏览 `bronze/`、`silver/`、`gold/` 前缀是否出现预期 Parquet 路径。
7. **SQL 确认**：浏览器打开 Trino UI 或使用 `docker exec -it slh-trino trino`，执行 `SHOW SCHEMAS FROM hive`、`SHOW TABLES IN hive.gold`、对 `hive.gold.ecb_dax_features` 与 `iceberg.gold.ecb_dax_features_iceberg` 做 `SELECT ... LIMIT 10` 对比。
8. **ML 确认**：打开 MLflow UI，确认实验与 run 已写入；若使用 Iceberg 路径读特征，对照 `ml/` 中 Trino 客户端用法（若存在）。
9. **停机策略**：日常结束用 `make down`；彻底重置演示环境用 `make clean`。

该流程将**健康检查**、**数据管道**、**三种 UI（MinIO、Trino、MLflow）** 与 **Dagster UI** 串成闭环，便于你向他人演示“湖仓 + 编排 + ML”的一体化故事。

---

## 二十八、Dagster 实例存储与 `dagster.yaml`

`dagster/dagster.yaml` 指定 `storage.postgres` 使用环境变量中的用户名、密码，并连接主机名 `postgres`、数据库名 `dagster_storage`。这意味着：

- **运行历史、传感器游标、调度状态**等持久化在 PostgreSQL 中，而不是仅存在于 Webserver 内存；
- 执行 `make clean` 会删除卷，**Dagster 历史也会一并清空**（与业务数据 MinIO 卷同时消失）。

若你在团队中共享一台 Docker 主机，需要区分**多套环境**，应为不同部署使用不同 Compose project 名或不同数据卷，避免 Dagster 元数据与 MinIO 路径混淆。

---

## 二十九、Trino 侧查询示例与“双表”阅读方式

在 Trino 中，同一套 Gold 数据可能以两种形式出现：

- **Hive 外部表** `hive.gold.ecb_dax_features`：直接指向 Parquet 目录，适合理解“湖上文件即表”的语义；
- **Iceberg 表** `iceberg.gold.ecb_dax_features_iceberg`：由 CTAS 从 Hive 表复制而来，用于演示 Iceberg 表格式与连接器行为。

典型查询（摘自 `docs/quickstart.md` / `docs/medallion-model.md` 的思路）：

```sql
SHOW CATALOGS;
SHOW SCHEMAS IN hive;
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 10;
```

若第二条失败，优先检查 Iceberg 是否已创建（`register_gold_tables_trino` 是否成功）、`iceberg` catalog 是否加载、以及 Trino 日志中是否有 S3 或 Metastore 相关错误。

---

## 三十、业务域简述：为何是 ECB 与 DAX

项目域为**欧洲央行利率**与**德国 DAX 指数**的公开数据（ADR-004）。ECB 侧通过 REST API 拉取，具备时间序列与政策事件语义；DAX 侧使用示例 CSV 模拟日频行情，便于离线演示。该组合的意义不在于金融预测准确性，而在于展示**多源对齐、事件研究特征、时间序列交叉验证（TimeSeriesSplit）** 等工程模式。阅读 `transformations/silver_to_gold_features.py` 与 `ml/train_ecb_dax_model.py` 可看到特征与标签如何构造。

---

## 三十一、`compose` 覆盖文件与 Profile 的作用（可选栈）

核心栈仅使用 `docker/docker-compose.yml`。  
**OpenMetadata** 通过 `docker-compose.openmetadata.yml` 叠加服务，并 `--profile openmetadata` 控制是否启动；避免默认 `make up` 就拉起重量级依赖。  
**Superset** 通过 `docker-compose.superset.yml` 叠加，并 `--profile superset`；且 `make up-superset` 会显式先 `up -d postgres` 再 bootstrap Superset 数据库，体现“元数据库与数据湖分离”的常见做法。

使用者只需记住：**核心命令不碰 OpenMetadata/Superset 也能完整跑通管道**；需要 BI 或数据目录演示时再启用 profile。

---

## 三十二、镜像构建缓存与“代码未进镜像”现象

Dagster、MLflow、Hive Metastore 使用本地 Dockerfile `build`。当你修改了 `ingestion/` 下 Python 但未 `docker compose build`，容器内仍是旧代码。排查方式：

- 显式 `docker compose -f docker/docker-compose.yml build dagster-webserver dagster-daemon`（或服务名等价物）；
- 或使用 `docker compose up -d --build`。

这与仅在本机 `pip install -r requirements.txt` 后跑 Legacy 脚本的行为不同，也是新手最容易混淆的点。

---

## 三十三、与 `make` 相关的环境变量钩子

- **`PIPELINE_MODE`**：`v2`（默认）走 Dagster；`v1` 或 `legacy` 走 `run-pipeline.py`。
- **`DAGSTER_JOB`**：默认 `full_pipeline_job`，若将来扩展多 Job 可切换。
- **`EXTRA_POSTGRES_DATABASES`**：由 `make up-superset` 传入，以逗号分隔附加数据库名。
- **`VERIFY_ENV`**：`make wait` 可传入额外环境变量（例如 Superset 检查开关），用于等待逻辑与验证脚本一致。

---

## 三十四、资源与卷的持久化清单（运维视角）

| 卷名 | 主要内容 |
|------|----------|
| `minio_data` | 所有业务 Parquet 与 MLflow artifact 对象 |
| `postgres_data` | Postgres 集群数据目录（含 Hive/MLflow/Dagster/可选 Superset 库） |
| `dagster_storage` | Dagster 本地计算/日志类路径（与 PG 配置并存，见 `dagster.yaml`） |

`make clean` 删除上述卷，**不可恢复**（除非你有外部备份）。演示前应对团队说明。

---

## 三十五、结语

SoloLakehouse 的部署与运行，本质上是 **Compose 编排的多容器数据平台** 与 **Dagster 驱动的批处理管道** 的组合：对象存储承载真实数据文件，Metastore 与 Trino 承载语义层与 SQL 访问，MLflow 承载实验可追溯性，Dagster 承载作业编排与自动化。理解各组件的契约（环境变量、端口、库名、路径约定），你就能在本地稳定复现、排障并安全地扩展。若你计划进入生产化阶段，请以 `docs/roadmap.md` 中 v3 治理与基础设施章节为下一跳，而不是在弱口令与单节点假设上叠加业务关键负载。

---

**文档版本说明**：本文撰写时对齐仓库中 `Makefile`、`docker/docker-compose.yml`、Dagster 定义与 `ingestion/trino_sql.py` 的行为；若上游分支变更服务名、Job 名或端口，请以当前仓库文件为准并相应更新本节。
