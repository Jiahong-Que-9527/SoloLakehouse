# SoloLakehouse：一个现代数据湖仓平台的完整解析

> 从源码到生产：一份面向外部陈述的深度技术叙事

---

## 目录

1. [项目定位与核心主张](#1-项目定位与核心主张)
2. [领域背景：为什么选择金融数据](#2-领域背景为什么选择金融数据)
3. [整体架构：五层核心模型](#3-整体架构五层核心模型)
4. [基础设施层：Docker Compose 编排的八服务平台](#4-基础设施层docker-compose-编排的八服务平台)
5. [存储层：MinIO 与对象存储哲学](#5-存储层minio-与对象存储哲学)
6. [数据摄入层：从外部世界到 Bronze](#6-数据摄入层从外部世界到-bronze)
7. [Schema 验证：Pydantic v2 驱动的数据契约](#7-schema-验证pydantic-v2-驱动的数据契约)
8. [Medallion 模型：Bronze、Silver、Gold 的完整实现](#8-medallion-模型bronzesilver-gold-的完整实现)
9. [特征工程：事件研究方法论的工程化](#9-特征工程事件研究方法论的工程化)
10. [查询层：Trino + Hive Metastore 的联邦架构](#10-查询层trino--hive-metastore-的联邦架构)
11. [表格式演进：Apache Iceberg 在 Gold 层的引入](#11-表格式演进apache-iceberg-在-gold-层的引入)
12. [机器学习层：MLflow 驱动的实验治理](#12-机器学习层mlflow-驱动的实验治理)
13. [编排层：Dagster 软件定义资产的全貌](#13-编排层dagster-软件定义资产的全貌)
14. [调度、传感器与资产检查：平台自动化的三根支柱](#14-调度传感器与资产检查平台自动化的三根支柱)
15. [可选扩展栈：OpenMetadata 与 Apache Superset](#15-可选扩展栈openmetadata-与-apache-superset)
16. [测试策略：无 Docker 单元测试与集成测试分层](#16-测试策略无-docker-单元测试与集成测试分层)
17. [配置管理：环境变量、模板与安全边界](#17-配置管理环境变量模板与安全边界)
18. [架构决策记录：每个技术选型的推理链](#18-架构决策记录每个技术选型的推理链)
19. [版本演进叙事：v1 → v2 → v3 的设计哲学](#19-版本演进叙事v1--v2--v3-的设计哲学)
20. [生产就绪性评估与 v3 展望](#20-生产就绪性评估与-v3-展望)
21. [快速上手指南](#21-快速上手指南)
22. [总结：这个 repo 教会我们什么](#22-总结这个-repo-教会我们什么)

---

## 1. 项目定位与核心主张

SoloLakehouse 是一个**完整可运行的湖仓（Lakehouse）架构参考实现**，它不是框架，不是库，不是平台产品，而是一个可以被克隆、运行、阅读和修改的真实工程仓库。

### 1.1 它解决了什么问题

在企业数据工程领域，Databricks 和 Snowflake 这类平台将复杂的基础设施抽象化，开发者只需关注 SQL 和 Python 逻辑。然而这种抽象的代价是：绝大多数使用这些平台的工程师并不真正理解底层是如何工作的。对象存储如何承载 Parquet 文件？Hive Metastore 在其中扮演什么角色？Trino 如何联邦查询多个数据目录？MLflow 如何将实验参数与制品存储关联？这些问题在托管平台中被完全隐藏。

SoloLakehouse 的核心主张是：**把这些隐藏的机制全部暴露出来，在一台机器上用开源工具完整复现企业级湖仓平台的内部结构**。

### 1.2 它不是什么

理解一个系统的边界与理解它能做什么同样重要。SoloLakehouse 明确声明：

- **不是生产框架**：它是参考实现，不是你在生产环境直接部署的产品。
- **不是流处理平台**：它专注批处理，Kafka/Flink 不在当前版本范围内。
- **不是多租户平台**：单节点 Docker Compose 设计，不处理水平扩展。
- **不是完整的企业数据目录**：OpenMetadata 是可选的演示扩展，不是必须组件。

### 1.3 定位受众

这个 repo 最适合以下几类人：

1. **数据工程师**：希望深入理解湖仓各组件如何协作，而不只是使用托管服务的接口。
2. **平台架构师**：需要一个可演示的参考架构来讨论技术选型决策（ADR 体系尤其有价值）。
3. **ML 工程师**：希望理解从原始数据到 MLflow 实验的完整工程路径。
4. **技术学习者**：用真实工程代码学习 Parquet、Trino、Dagster、MLflow 的集成模式。

---

## 2. 领域背景：为什么选择金融数据

### 2.1 数据源的选择标准

在构建参考实现时，数据源的选择至关重要。理想的教学数据需要满足：

- **公开可访问**：无需 API Key、无需付费，任何人任何时候都能重现。
- **结构化且有时序性**：能够展示时间序列处理、窗口计算等工程技术。
- **两个可关联的独立来源**：能够演示跨源 Join 和特征工程。
- **数据量适中**：既够做真实计算，又不会超出单节点内存限制。

### 2.2 ECB 利率数据（主数据源）

**欧洲央行（European Central Bank）主要再融资操作（Main Refinancing Operations，MRO）利率**是第一个数据源。

- **来源**：ECB 统计数据仓库（Statistical Data Warehouse，SDW）REST API
- **端点**：`https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.MRR_RT.LEV`
- **内容**：1999 年至今，欧元区基准利率的每日观测值（以百分比表示）
- **特征**：稀疏时间序列——ECB 不每天变更利率，大部分日期的值与前一天相同；真正的利率决议（rate change events）在整个数据集中只有几十次

这种稀疏性实际上是一个非常好的教学设计：它强制工程师处理前向填充（forward fill）、事件识别和窗口函数等真实场景。

### 2.3 DAX 指数数据（次数据源）

**德国 DAX 股票指数（Deutscher Aktienindex）**日线数据是第二个数据源。

- **来源**：仓库中提交的样本 CSV 文件（`data/sample/dax_daily_sample.csv`）
- **内容**：OHLCV 数据（开盘价、最高价、最低价、收盘价、成交量）
- **设计意图**：模拟真实市场数据管道中 "从文件系统读取定期交付文件" 的场景

DAX 作为欧洲主要股票指数，与 ECB 货币政策存在宏观经济关联——这为后续的机器学习实验提供了真实的业务假设：**欧洲央行的利率决议是否影响 DAX 的短期走势？**

### 2.4 事件研究方法论

这两个数据源的组合实现了金融分析中的经典方法：**事件研究（Event Study）**。

事件研究方法论的核心思路是：以某个重大事件（这里是 ECB 利率决议）为基准点，测量目标资产（这里是 DAX 指数）在事件前后一定窗口期内的异常收益（abnormal return）。

具体到这个实现：
- **事件日**：ECB 发布利率变更决议的日期（`rate_change_bps != 0`）
- **pre-window**：事件日前 5 个交易日（用于计算基准收益率和波动率）
- **post-window**：事件日后 1 和 5 个交易日（用于衡量市场反应）
- **特征变量**：利率变动幅度（basis points）、变动方向（加息/降息）、事件前市场波动率

这一方法论直接影响了 Gold 层的特征工程设计，我们将在后续章节详细展开。

---

## 3. 整体架构：五层核心模型

### 3.1 架构全图

SoloLakehouse 的架构可以被描述为一个**垂直的数据流水线**，从外部数据源开始，向下穿越五个功能层，最终在 ML 跟踪层落地：

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Data Sources                                  │
│  ECB SDW API (REST)  │  DAX CSV (File)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / File I/O
┌──────────────────────▼──────────────────────────────────┐
│  Layer 2: Ingestion & Validation                        │
│  ECBCollector  │  DAXCollector                          │
│  Pydantic v2 Schema Validation                          │
│  Bronze Quality Checks                                  │
└──────────────────────┬──────────────────────────────────┘
                       │ Parquet (snappy) over S3 API
┌──────────────────────▼──────────────────────────────────┐
│  Layer 3: Lakehouse Storage (MinIO)                     │
│  Bronze (raw, immutable, partitioned by date)           │
│  Silver (cleaned, typed, deduplicated)                  │
│  Gold   (event-study feature table)                     │
└──────────────────────┬──────────────────────────────────┘
                       │ Thrift / SQL
┌──────────────────────▼──────────────────────────────────┐
│  Layer 4: Metadata & Query                              │
│  Hive Metastore (PostgreSQL-backed)                     │
│  Trino (Hive catalog + Iceberg catalog)                 │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / Parquet artifacts
┌──────────────────────▼──────────────────────────────────┐
│  Layer 5: ML Tracking                                   │
│  MLflow (PostgreSQL backend + MinIO artifacts)          │
│  XGBoost / LightGBM experiments                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 编排层（v2 新增）

v2 在五层核心之上增加了**Dagster 编排层**，它不替换任何一层的功能，而是在这五层之上建立了**资产图（asset graph）、调度（schedule）、传感器（sensor）和资产检查（asset check）**的平台语义。

```
┌─────────────────────────────────────────────────────────┐
│  Orchestration Layer (v2): Dagster                      │
│  dagster-webserver (UI + execution, port 3000)          │
│  dagster-daemon (schedule/sensor evaluation)            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Asset Graph: ecb_bronze → ecb_silver ──┐       │   │
│  │               dax_bronze → dax_silver ──┼──► gold_features → ml_experiment │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.3 v1 与 v2 的层次关系

这里有一个重要的设计决策值得强调：**v2 的 Dagster 层不重写任何数据逻辑**。所有的采集、转换、特征工程和 ML 训练代码在 v1 中就已经存在，v2 只是给这些代码加上了编排包装。

这意味着运行 `make pipeline-v1`（v1 线性脚本）和 `make pipeline`（v2 Dagster 作业）产生**完全相同的数据输出**。区别仅在于：前者是一个 Python 脚本按顺序调用六个函数；后者是一个有依赖图、有调度、有重试、有可视化 UI 的平台级操作。

---

## 4. 基础设施层：Docker Compose 编排的八服务平台

### 4.1 服务清单

整个平台由 8 个 Docker 容器组成，全部通过 `docker/docker-compose.yml` 声明和管理：

| 容器名 | 镜像 | 作用 | 端口 |
|--------|------|------|------|
| `slh-minio` | MinIO | S3 兼容对象存储 | 9000 (API), 9001 (Console) |
| `slh-minio-init` | MinIO Client | 初始化 bucket（一次性） | — |
| `slh-postgres` | PostgreSQL 17 | 元数据后端（多租户） | 5432 |
| `slh-hive-metastore` | Apache Hive 4.0.0 | 表目录元数据服务 | 9083 |
| `slh-trino` | Trino 480 | 联邦 SQL 查询引擎 | 8080 |
| `slh-mlflow` | MLflow 3.10.1 | ML 实验跟踪 | 5000 |
| `slh-dagster-webserver` | Dagster | 编排 UI + 执行引擎 | 3000 |
| `slh-dagster-daemon` | Dagster | 调度/传感器后台进程 | — |

### 4.2 服务依赖拓扑

服务之间的依赖关系并不是简单的线性链，而是一个有层次的有向无环图：

```
postgres ──────────────────────────────────────────────┐
    │                                                   │
    ├──► hive-metastore ────────────────────────────┐  │
    │         │                                     │  │
    │         └──► trino ───────────────────────────┤  │
    │                                               │  │
    ├──► mlflow ────────────────────────────────────┤  │
    │                                               │  │
    └──► dagster-webserver ─────────────────────────┤  │
              │                                     │  │
              └──► dagster-daemon                   │  │
                                                    │  │
minio ──────────────────────────────────────────────┘  │
minio-init (depends: minio) ───────────────────────────┘
```

**PostgreSQL 是整个平台的核心元数据后端**，它同时服务于：
- `hive_metastore` 数据库：Hive Metastore 存储 Trino 可查询的表定义
- `mlflow` 数据库：MLflow 存储实验运行的参数和指标
- `dagster_storage` 数据库：Dagster 持久化管线运行历史和事件日志

这是一个刻意的设计——在单节点参考实现中，共享同一个 PostgreSQL 实例既降低了资源开销，也展示了多个数据系统如何共享关系型元数据后端这一真实模式。

### 4.3 健康检查机制

每个服务都配置了 Docker 健康检查，`make up` 命令在所有服务变为 `healthy` 状态后才返回。健康检查策略因服务类型而异：

- **MinIO**：`curl -f http://minio:9000/minio/health/live`
- **PostgreSQL**：`pg_isready -U postgres`
- **Trino**：检查 `/v1/info` 端点，等待状态从 `STARTING` 变为 `RUNNING`
- **MLflow**：`curl -f http://mlflow:5000`
- **Dagster webserver**：`curl -f http://dagster-webserver:3000/server_info`（带 60 秒 `start_period`）

Dagster 的 60 秒 `start_period` 是基于实际经验设置的——Dagster 加载代码位置（code location）需要时间，在此期间健康检查会返回非成功状态，过短的 `start_period` 会导致容器被误判为不健康并重启。

### 4.4 minio-init：幂等初始化模式

`minio-init` 容器是一个值得注意的设计模式：

```yaml
minio-init:
  image: minio/mc
  depends_on:
    minio:
      condition: service_healthy
  restart: no
  entrypoint: >
    /bin/sh -c "
    mc alias set slh http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD &&
    mc mb --ignore-existing slh/sololakehouse &&
    mc mb --ignore-existing slh/mlflow-artifacts
    "
```

关键点：
- `restart: no`：只执行一次，不像其他服务那样在失败后重启
- `--ignore-existing`：创建 bucket 时忽略 "已存在" 错误，实现幂等性
- `depends_on: condition: service_healthy`：只在 MinIO 完全就绪后才开始初始化

这是 Docker Compose 中实现 "一次性初始化" 的标准模式，类比 Kubernetes 中的 Init Container。

### 4.5 Trino 的模板化配置

Trino catalog 配置文件（`config/trino/catalog/hive.properties`）使用 `${VAR}` 占位符存储凭据：

```properties
connector.name=hive
hive.metastore.uri=thrift://hive-metastore:9083
hive.s3.endpoint=http://minio:9000
hive.s3.aws-access-key=${S3_ACCESS_KEY}
hive.s3.aws-secret-key=${S3_SECRET_KEY}
hive.s3.path-style-access=true
```

容器启动时，`scripts/trino-entrypoint.sh` 使用 bash 的 `eval` 和 `envsubst` 展开所有 catalog 模板文件，然后再启动 Trino 进程。这样既避免了将凭据硬编码到镜像中，又保留了纯文本模板的可读性。

---

## 5. 存储层：MinIO 与对象存储哲学

### 5.1 为什么选择对象存储

现代湖仓架构的核心理念之一是**存储与计算分离**。传统的数据仓库将存储和查询引擎紧密耦合（如 Teradata、早期 Vertica），这导致扩展成本高、灵活性差。

S3 兼容的对象存储（AWS S3 / Azure ADLS / GCP GCS / MinIO）改变了这一格局：

- **无限水平扩展**：存储容量独立于计算资源扩展
- **廉价持久性**：以远低于块存储的成本实现高可靠性
- **标准化接口**：S3 API 成为数据湖存储的事实标准
- **任意格式**：存储 Parquet、ORC、Avro、JSON 等任何格式的文件

MinIO 在这里的作用就是**在本地模拟 AWS S3**，使得所有针对 S3 API 编写的代码无需任何修改就能在本地运行。

### 5.2 Parquet：列式存储的选择

所有数据以 **Apache Parquet 格式（Snappy 压缩）**存储。为什么是 Parquet？

1. **列式存储**：分析查询通常只需要少数几列，列式格式避免了读取无关列的 I/O
2. **内置元数据**：每个 Parquet 文件包含 schema 信息、行数、列统计（min/max/null count），查询引擎利用这些信息进行谓词下推（predicate pushdown）
3. **压缩效率**：相同数据用 Snappy 压缩后通常只有原始 CSV 的 20-30%
4. **生态兼容性**：Pandas、PyArrow、Trino、Spark、DuckDB 全部原生支持 Parquet

### 5.3 Bucket 结构

MinIO 中有两个 bucket：

**`sololakehouse`**：存储所有数据层的 Parquet 文件
```
sololakehouse/
├── bronze/
│   ├── ecb_rates/
│   │   └── ingestion_date=2024-01-15/
│   │       └── ecb_rates.parquet
│   ├── dax_daily/
│   │   └── ingestion_date=2024-01-15/
│   │       └── dax_daily.parquet
│   └── rejected/
│       ├── source=ECB/
│       │   └── ingestion_date=2024-01-15/
│       │       └── rejected.parquet
│       └── source=DAX/
│           └── ...
├── silver/
│   ├── ecb_rates_cleaned/
│   │   └── ecb_rates_cleaned.parquet
│   └── dax_daily_cleaned/
│       └── dax_daily_cleaned.parquet
└── gold/
    └── rate_impact_features/
        └── ecb_dax_features.parquet
```

**`mlflow-artifacts`**：存储 MLflow 实验产生的模型文件和制品

### 5.4 分区策略：Bronze 按摄入日期分区

Bronze 层按 `ingestion_date=YYYY-MM-DD` 分区这一设计具有几个重要含义：

1. **不可变性保证**：每次运行生成一个新分区，永远不覆盖历史数据
2. **增量检测**：通过列举分区目录可以快速判断今天是否已经摄入
3. **调试可追溯性**：可以回溯到任意一天摄入的原始数据
4. **Hive 兼容分区裁剪**：Hive Metastore 和 Trino 可以利用分区目录名进行分区裁剪

这一分区命名约定（`key=value`）是 Hive 的约定，同时也是 Spark、Pandas（`pd.read_parquet` 自动识别）和 PyArrow 支持的标准格式。

---

## 6. 数据摄入层：从外部世界到 Bronze

### 6.1 Collector 模式

摄入层采用了一个称为 "Collector 模式" 的设计，每个数据源对应一个独立的 Collector 类。这一模式的职责边界非常清晰：

```
class ECBCollector:
    _fetch_data()        # 网络 I/O：从外部 API 获取原始数据
    _parse_payload()     # 数据解析：将 API 响应转换为记录列表
    _validate_records()  # Schema 验证：逐条通过 Pydantic 验证
    _already_ingested_today()  # 幂等检查：今天是否已经摄入
    collect()            # 编排：协调上述步骤，返回摘要 dict
```

这种设计的优点是：每个方法都有单一职责，可以独立测试，可以独立替换（比如换一个 API 端点而不改变验证逻辑）。

### 6.2 ECBCollector 详解

让我们深入 ECBCollector 的实现来理解实际工程细节。

**数据获取与重试**

```python
def _fetch_data(self) -> list[dict[str, Any]]:
    params = {"format": "jsondata", "startPeriod": "1999-01-01"}
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            response = requests.get(self.ENDPOINT, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            return self._parse_payload(payload)
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2)

    raise CollectorUnavailableError(
        f"ECB source unreachable after 3 retries: {last_error}"
    ) from last_error
```

这里有几个值得注意的工程实践：

1. **固定重试次数（3次）**：不使用指数退避（exponential backoff）是一个刻意的简化选择。ECB API 的不稳定通常是临时性的，2 秒固定间隔对于批处理场景已经足够。
2. **自定义异常类型**：`CollectorUnavailableError` 让上层调用者（Dagster asset）能够精确捕获网络不可用的情况，而不是捕获通用的 `Exception`。
3. **`startPeriod=1999-01-01`**：欧元于 1999 年正式启动，这是 ECB MRO 利率的起始日期。每次都拉取全量历史数据——这对于一个每天数据量不超过几 KB 的 API 是合理的。
4. **`timeout=10`**：10 秒超时防止网络问题导致无限等待。

**ECB API 响应解析**

ECB 的 SDMX-JSON 格式并不直观，需要手动构建日期索引：

```python
def _parse_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    observation_values = (
        payload.get("structure", {})
        .get("dimensions", {})
        .get("observation", [{}])[0]
        .get("values", [])
    )
    index_to_date = {
        str(idx): entry.get("id")
        for idx, entry in enumerate(observation_values)
        if entry.get("id")
    }
    ...
```

ECB 的 JSON 响应将时间维度编码为索引（0, 1, 2...），而不是直接的日期字符串。`index_to_date` 字典将这些整数索引映射到实际的 ISO 日期字符串，是理解这段代码的关键。

**幂等性检查**

```python
def _already_ingested_today(self) -> bool:
    today = dt.date.today().isoformat()
    pattern = re.compile(r"ingestion_date=(\d{4}-\d{2}-\d{2})/")
    latest_partition: str | None = None

    objects = self.minio.list_objects(
        self.bucket, prefix="bronze/ecb_rates/", recursive=True
    )
    for obj in objects:
        match = pattern.search(obj.object_name)
        if match:
            date_str = match.group(1)
            if latest_partition is None or date_str > latest_partition:
                latest_partition = date_str

    return latest_partition == today
```

这个方法通过列举 MinIO 中的对象名称并用正则表达式提取分区日期来判断是否已经运行过。注意它找的是 **最新** 分区日期而不是任意分区——这防止了 "历史某天的数据存在" 被误判为 "今天已摄入"。

### 6.3 DAXCollector：文件摄入模式

相比 ECBCollector 的 API 拉取，DAXCollector 读取本地 CSV 文件，展示了另一种常见的摄入场景——定期交付的文件：

```python
class DAXCollector:
    DATA_PATH = "data/sample/dax_daily_sample.csv"

    def _fetch_data(self) -> pd.DataFrame:
        return pd.read_csv(self.DATA_PATH, parse_dates=["Date"])
```

DAX 数据使用提交到仓库的样本 CSV，这是一个刻意的设计选择。在真实场景中，这可能是从 Bloomberg、Refinitiv 或交易所 FTP 服务器定期下载的文件。使用样本文件让每个人都能在没有订阅的情况下复现完整的管道。

### 6.4 BronzeWriter：统一的 Parquet 写入接口

两个 Collector 都通过 `BronzeWriter` 类将验证后的数据写入 MinIO：

```python
class BronzeWriter:
    def write(self, df: pd.DataFrame, source: str) -> str:
        today = date.today().isoformat()
        path = f"bronze/{source}/ingestion_date={today}/{source}.parquet"

        buffer = BytesIO()
        pq.write_table(
            pa.Table.from_pandas(df),
            buffer,
            compression="snappy"
        )
        buffer.seek(0)
        self.minio.put_object(
            self.bucket, path, buffer,
            length=buffer.getbuffer().nbytes
        )
        return path

    def write_rejected(self, rejected: list[dict], source: str) -> str | None:
        if not rejected:
            return None
        # 将拒绝记录写入 bronze/rejected/ 而不是丢弃
        ...
```

`write_rejected` 方法体现了一个重要的数据工程原则：**永远不要静默丢弃数据**。未通过验证的记录会被写入专门的拒绝分区，保留拒绝原因，使得后续的数据质量分析成为可能。

---

## 7. Schema 验证：Pydantic v2 驱动的数据契约

### 7.1 为什么在摄入层做 Schema 验证

在数据进入 Bronze 层之前就执行 Schema 验证是湖仓架构的最佳实践之一，原因在于：

**"Bronze 即原始数据" 这个说法是有前提的**：原始数据应该是 *来自外部的真实数据*，而不是包含类型错误、超范围值或格式异常的垃圾数据。通过在边界处验证，我们保证了 Bronze 层的数据质量基线，使得下游的 Silver/Gold 转换可以信任输入数据的结构和基本质量。

### 7.2 ECBRecord：精确的领域约束

```python
class ECBRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    observation_date: dt.date
    rate_pct: float
    ingestion_timestamp: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.UTC),
        serialization_alias="_ingestion_timestamp",
    )
    source: str = Field(default="ECB_SDW", serialization_alias="_source")

    @field_validator("observation_date")
    @classmethod
    def validate_observation_date_not_future(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("observation_date must not be in the future")
        return value

    @field_validator("rate_pct")
    @classmethod
    def validate_rate_pct_range(cls, value: float) -> float:
        if not -5.0 <= value <= 20.0:
            raise ValueError("rate_pct must be between -5.0 and 20.0")
        return value
```

这里有几个工程决策值得解析：

1. **`observation_date: dt.date`**：类型是 `date` 而不是 `str`。Pydantic v2 自动将 `"2024-01-15"` 字符串解析为 `datetime.date` 对象，并在解析失败时抛出 `ValidationError`。

2. **`rate_pct` 范围 [-5.0, 20.0]**：这个范围基于 ECB 利率的历史值。历史上 ECB 的 MRO 利率最高约为 4.75%（2000年），但为了未来兼容性留了足够的边距。负利率（如 ECB 在 2014-2022 年间实施的 -0.5%）也被合理覆盖。

3. **`ingestion_timestamp` 自动注入**：每条记录都会自动获得摄入时间戳，使用 UTC 时区（`dt.UTC`）。这是数据可追溯性的基础。

4. **`serialization_alias="_ingestion_timestamp"`**：序列化时（`.model_dump(by_alias=True)`）字段名带下划线前缀，这是一种常见约定，用于区分 "来自原始数据的字段" 和 "由管道添加的元数据字段"。

5. **`populate_by_name=True`**：允许同时使用原始字段名和别名来填充模型，保持灵活性。

### 7.3 Bronze 质量检查：超出 Schema 的业务规则

Pydantic 验证处理的是**字段级别**的约束。`bronze_checks.py` 实现了**数据集级别**的质量规则：

```python
def check_no_future_dates(df: pd.DataFrame, date_col: str) -> None:
    """确保没有未来日期"""

def check_date_continuity(df: pd.DataFrame, date_col: str,
                          max_gap_days: int) -> None:
    """检测时间序列中超过阈值的日期间隔"""

def check_no_nulls(df: pd.DataFrame, required_cols: list[str]) -> None:
    """确保关键字段没有空值"""

def check_schema_version(df: pd.DataFrame, expected_cols: list[str]) -> None:
    """验证所有期望的列都存在"""
```

注意 ECB 和 DAX 的日期连续性阈值不同：
- ECB 利率数据：`max_gap_days=180`（ECB 不是每天都开会，180天的间隔意味着超过 6 个月没有观测值，这在历史上不可能发生）
- DAX 数据：`max_gap_days=5`（股市休市通常不超过一个交易周，超过5天说明数据有问题）

这些质量检查在**发现异常时抛出异常**，而不是记录警告然后继续。这是 "快速失败（fail-fast）" 原则的体现——在数据质量问题被引入管道之初就终止运行，而不是让问题传播到下游才被发现。

---

## 8. Medallion 模型：Bronze、Silver、Gold 的完整实现

### 8.1 Medallion 模型的设计哲学

Medallion（金属层次）模型是 Databricks 推广的数据架构范式，其核心思想是：**对数据在不同成熟度阶段进行分层存储，每一层都有明确的质量级别和转换语义**。

SoloLakehouse 完整实现了三层 Medallion 模型，下面我们逐层分析。

### 8.2 Bronze 层：原始性与不可变性

**Bronze 是系统的 "事实" 来源（source of truth for raw data）**。它的核心约束是：

- **不可变（Immutable）**：一旦写入，永不修改。新数据只能追加新分区。
- **接近原始（Near-raw）**：保留数据在来源处的结构，只做必要的 Schema 验证。
- **完整保留（Complete retention）**：包括被拒绝的记录，都保存在 `bronze/rejected/` 中。

Bronze 层的存储路径体现了这一哲学：

```
bronze/ecb_rates/ingestion_date=2024-01-15/ecb_rates.parquet
```

每次运行都生成一个带日期分区的新文件。如果同一天需要重新摄入（使用 `--force` 参数），新文件会覆盖同一分区，但不会影响其他分区的历史数据。

### 8.3 Silver 层：清洗与标准化

**Silver 是系统的 "真相" 来源（source of truth for business-ready data）**。转换规则：

**ECB Silver（`ecb_bronze_to_silver.py`）**：

```python
def transform_ecb_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()  # 永不修改输入

    # 1. 类型转换
    df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
    df["rate_pct"] = pd.to_numeric(df["rate_pct"], errors="coerce")

    # 2. 排序
    df = df.sort_values("observation_date")

    # 3. 前向填充（处理 ECB 不更改利率的日期）
    df["rate_pct"] = df["rate_pct"].ffill()

    # 4. 计算利率变动幅度（基点）
    df["rate_change_bps"] = (df["rate_pct"] - df["rate_pct"].shift(1)) * 100

    # 5. 去重（以观测日期为键）
    df = df.drop_duplicates(subset=["observation_date"])

    # 6. 返回明确的列子集
    return df[["observation_date", "rate_pct", "rate_change_bps"]]
```

**前向填充（ffill）的必要性**：ECB 的原始 API 数据只在利率实际变更的日期才有值，其他日期没有记录（或者说记录了前一个值但 API 可能不完整）。前向填充将这些稀疏观测值转化为完整的日度时间序列，这对于后续与每日 DAX 数据的 Join 至关重要。

**`rate_change_bps` 的计算**：`(rate_pct - lag(rate_pct)) * 100` 给出每日的基点变化量（basis points，1 BP = 0.01%）。大多数日期这个值为 0（利率未变），只在 ECB 宣布利率决议的日期才有非零值。

**DAX Silver（`dax_bronze_to_silver.py`）**：

```python
def transform_dax_bronze_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 类型转换
    df["observation_date"] = pd.to_datetime(df["Date"]).dt.date
    price_cols = ["open_price", "high_price", "low_price", "close_price"]
    for col in price_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 过滤周末（weekday < 5 表示周一至周五）
    df = df[df["observation_date"].map(
        lambda d: d.weekday() < 5
    )]

    # 计算日收益率
    df = df.sort_values("observation_date")
    df["daily_return"] = (
        df["close_price"] / df["close_price"].shift(1) - 1
    ) * 100

    # 去重
    df = df.drop_duplicates(subset=["observation_date"])

    return df[["observation_date", "open_price", "high_price",
               "low_price", "close_price", "volume", "daily_return"]]
```

过滤周末是必要的，因为股票市场在周末不交易，但如果原始数据包含周末记录（数据质量问题），需要明确过滤掉。

### 8.4 Gold 层：特征工程与分析就绪

Gold 层是整个 Medallion 模型的顶端，也是最体现业务逻辑的一层。在 SoloLakehouse 中，Gold 层实现了基于事件研究方法论的特征工程——这将在下一章专门展开。

---

## 9. 特征工程：事件研究方法论的工程化

### 9.1 问题定义

Gold 层回答一个具体的业务问题：

> **当欧洲央行改变基准利率时，DAX 指数在接下来的 1 个交易日和 5 个交易日会如何反应？能否用利率变动的特征预测市场反应方向？**

将这个问题转化为机器学习问题：

- **一条训练样本**：一次 ECB 利率决议事件
- **特征（X）**：利率变动幅度、变动方向、事件前市场波动率、利率水平
- **标签（y）**：事件后 1 天 DAX 是否上涨（二分类）

Gold 层的任务就是构造这样的特征矩阵。

### 9.2 build_gold_features 的核心算法

```python
def build_gold_features(ecb_df: pd.DataFrame, dax_df: pd.DataFrame) -> pd.DataFrame:
    # 步骤1：识别利率变动事件
    events = ecb[ecb["rate_change_bps"].fillna(0) != 0].sort_values("observation_date")

    rows = []
    for _, event in events.iterrows():
        event_date = event["observation_date"]

        # 步骤2：找到事件日之后最近的 DAX 交易日（3天窗口）
        candidates = dax[
            (dax["observation_date"] >= event_date) &
            (dax["observation_date"] <= event_date + timedelta(days=3))
        ]
        if candidates.empty:
            continue

        event_dax_idx = int(candidates.index[0])

        # 步骤3：提取前后窗口（各5个交易日）
        prev_window = dax.iloc[max(0, event_dax_idx - 5):event_dax_idx]
        post_window = dax.iloc[event_dax_idx + 1:event_dax_idx + 6]

        # 步骤4：数据完整性检查
        if len(prev_window) < 5 or len(post_window) < 5:
            continue

        # 步骤5：计算特征
        dax_pre_close = prev_window.iloc[-1]["close_price"]
        dax_return_1d = dax.iloc[event_dax_idx]["daily_return"]
        dax_return_5d = _compute_cumulative_return_pct(post_window["daily_return"])
        dax_volatility_pre_5d = float(prev_window["daily_return"].std())

        row = {
            "event_date": event_date,
            "rate_change_bps": float(event["rate_change_bps"]),
            "rate_level_pct": float(event["rate_pct"]),
            "is_rate_hike": bool(event["rate_change_bps"] > 0),
            "is_rate_cut": bool(event["rate_change_bps"] < 0),
            "dax_pre_close": float(dax_pre_close),
            "dax_return_1d": float(dax_return_1d),
            "dax_return_5d": float(dax_return_5d),
            "dax_volatility_pre_5d": dax_volatility_pre_5d,
        }
        rows.append(row)
```

### 9.3 关键工程决策的分析

**为什么用 "最近交易日" 而不是 "精确事件日"？**

ECB 利率决议通常在周四宣布，但有时也在其他工作日。然而，即使是工作日宣布的决议，DAX 的当天数据可能还没有收盘（如果决议在下午宣布，那天的 DAX 数据要晚些才能获取）。使用 3 天窗口内的最近交易日是一种鲁棒性设计，处理了事件日和交易日之间的潜在不对齐。

**5 个交易日的前后窗口**

前 5 日用于计算 "背景波动率"（市场在此次决议前的正常波动水平），后 5 日用于测量累积影响。这是事件研究中的标准窗口设置，足够捕捉短期市场反应，同时避免与其他宏观事件的混淆。

**`_compute_cumulative_return_pct` 的正确性**

```python
def _compute_cumulative_return_pct(returns_pct: pd.Series) -> float:
    gross = (1.0 + (returns_pct / 100.0)).prod()
    return float((gross - 1.0) * 100.0)
```

这里使用的是**几何复利公式**而非简单求和。假设5天收益率分别为 1%，-1%，2%，-2%，1%：
- 简单求和：1%
- 几何复利：`(1.01)(0.99)(1.02)(0.98)(1.01) - 1 ≈ 0.97%`

对于较小的收益率，两者差异不大，但几何复利才是财务分析中的正确方法，体现了对金融领域知识的尊重。

**数据完整性检查的必要性**

```python
if len(prev_window) < 5 or len(post_window) < 5:
    continue
```

如果某个事件发生在数据集的开头或结尾，可能没有足够的前置或后置数据来计算特征。这个检查确保了特征工程只处理有完整数据支持的事件，宁可减少样本量也不接受不完整的特征。

### 9.4 Gold 层的双重注册

Gold Parquet 文件写入 MinIO 后，还需要通过 Trino 注册为可查询的表：

```
Gold Parquet (MinIO: gold/rate_impact_features/ecb_dax_features.parquet)
        │
        ├──► Hive 外部表: hive.gold.ecb_dax_features
        │    （通过 CREATE TABLE ... WITH (external_location=...) ）
        │
        └──► Iceberg 表: iceberg.gold.ecb_dax_features_iceberg
             （通过 CREATE TABLE ... AS SELECT FROM hive.gold.ecb_dax_features ）
```

`ingestion/trino_sql.py` 中的 `register_gold_tables_trino` 函数负责这一注册流程，包含了对 Trino 可能出现的 "表已存在" 等瞬态错误的处理逻辑。

---

## 10. 查询层：Trino + Hive Metastore 的联邦架构

### 10.1 为什么需要 Trino？

在拥有 MinIO 对象存储和 Parquet 文件之后，为什么还需要 Trino？这个问题触及了湖仓架构的核心价值主张。

**没有 Trino**，你只能通过 Python（PyArrow/Pandas）直接读取 Parquet 文件。这对于批处理作业是可行的，但有几个限制：

1. **无法用 SQL 交互式探索数据**：数据分析师不会 Python，或者不应该为了探索数据而编写 Python 代码
2. **无法跨文件 Join**：Pandas 的 `read_parquet` 一次读取一个文件，跨分区 Join 需要手动代码
3. **没有统一的数据字典**：如果不告诉别人哪个路径是什么表，Parquet 文件只是无结构的二进制文件

**有了 Trino**，所有数据都变成了可以用标准 SQL 查询的"表"：

```sql
-- 找出所有加息事件后 DAX 表现
SELECT event_date, rate_change_bps, dax_return_5d
FROM hive.gold.ecb_dax_features
WHERE is_rate_hike = true
ORDER BY dax_return_5d DESC;
```

### 10.2 Hive Metastore 的角色

Hive Metastore（HMS）是 Trino 能够将 MinIO 中的 Parquet 文件识别为"表"的关键。HMS 存储了：

- 表名 → S3 路径的映射
- 列名、数据类型、分区信息
- 表的属性（文件格式、SerDe 等）

HMS 使用 PostgreSQL 的 `hive_metastore` 数据库持久化这些元数据。Trino 在执行 SQL 查询时，先查询 HMS 获取表的物理位置和 Schema，再去 MinIO 读取实际的 Parquet 数据。

这个架构的美妙之处在于：**MinIO 只是哑存储，HMS 只是元数据服务，Trino 才是计算引擎**——三者完全解耦，可以独立扩展替换。

### 10.3 Trino 的双 Catalog 架构

SoloLakehouse 中 Trino 配置了两个 catalog：

**hive catalog**（`config/trino/catalog/hive.properties`）：
```properties
connector.name=hive
hive.metastore.uri=thrift://hive-metastore:9083
hive.s3.endpoint=http://minio:9000
hive.s3.aws-access-key=${S3_ACCESS_KEY}
hive.s3.aws-secret-key=${S3_SECRET_KEY}
hive.s3.path-style-access=true
```

使用 Thrift 协议连接 Hive Metastore，读取 `gold/`、`silver/`、`bronze/` 中的 Parquet 表。

**iceberg catalog**（`config/trino/catalog/iceberg.properties`）：
```properties
connector.name=iceberg
hive.metastore.uri=thrift://hive-metastore:9083
hive.s3.endpoint=http://minio:9000
...
```

同样使用 Hive Metastore 作为 Iceberg 的 catalog 后端（HMS 不仅服务于传统 Hive，也可以作为 Iceberg catalog），但通过 Iceberg connector 提供 ACID 事务、时间旅行等增强能力。

### 10.4 查询路径分析

当用户执行：

```sql
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
```

Trino 的内部执行路径如下：

1. **解析**：`hive` catalog，`gold` schema，`ecb_dax_features` 表
2. **元数据查询**：Trino Coordinator 向 HMS（Thrift 9083）查询表的 S3 位置和 Schema
3. **Split 规划**：HMS 返回 `s3a://sololakehouse/gold/rate_impact_features/ecb_dax_features.parquet`，Trino 将其规划为一个或多个 Split
4. **数据读取**：Trino Worker 从 MinIO（HTTP 9000）读取 Parquet 文件
5. **列投影**：使用 Parquet 内置的列元数据，只读取 `LIMIT 10` 需要的数据
6. **结果返回**：通过 HTTP 返回给客户端

整个过程中，MinIO、HMS、Trino 三者通过标准协议（S3 API、Thrift RPC、HTTP）通信，完全无需 JVM 级别的共享内存或特殊集成。

---

## 11. 表格式演进：Apache Iceberg 在 Gold 层的引入

### 11.1 从 Parquet 文件到表格式

原生 Parquet 是"哑"存储：它没有事务性、没有 schema evolution 跟踪、没有时间旅行、没有统一的 snapshot 管理。当多个写入者同时操作时，会出现一致性问题。

Apache Iceberg 通过在 Parquet 之上增加一层**元数据管理**解决了这些问题：

```
iceberg table
├── metadata/
│   ├── v1.metadata.json    ← snapshot 1 的元数据
│   ├── v2.metadata.json    ← snapshot 2 的元数据
│   └── current.metadata.json  ← 指向当前版本
├── data/
│   ├── part-00001.parquet
│   └── part-00002.parquet
└── manifests/
    └── *.avro              ← 文件列表和统计信息
```

Iceberg 的核心能力：
- **ACID 事务**：写操作要么完全成功要么完全回滚
- **时间旅行（Time Travel）**：`SELECT * FROM table FOR SYSTEM_VERSION AS OF <snapshot_id>`
- **Schema Evolution**：安全地添加、删除、重命名列
- **Hidden Partitioning**：分区策略对查询者透明

### 11.2 SoloLakehouse v2.5 的 Iceberg 实现

v2.5 将 Gold 层数据同时注册为 Hive 外部表和 Iceberg 表：

**Hive 外部表（用于向后兼容）**：
```sql
CREATE TABLE IF NOT EXISTS hive.gold.ecb_dax_features (
    event_date DATE,
    rate_change_bps DOUBLE,
    rate_level_pct DOUBLE,
    is_rate_hike BOOLEAN,
    is_rate_cut BOOLEAN,
    dax_pre_close DOUBLE,
    dax_return_1d DOUBLE,
    dax_return_5d DOUBLE,
    dax_volatility_pre_5d DOUBLE
)
WITH (
    format = 'PARQUET',
    external_location = 's3a://sololakehouse/gold/rate_impact_features/'
)
```

**Iceberg CTAS（从 Hive 表创建 Iceberg 表）**：
```sql
CREATE OR REPLACE TABLE iceberg.gold.ecb_dax_features_iceberg
AS SELECT * FROM hive.gold.ecb_dax_features
```

这一设计的优雅之处在于：Gold Parquet 文件只写一次，然后通过 Trino CTAS 将数据 "提升" 到 Iceberg 格式，无需重新运行上游管道。

### 11.3 ML 实验中优先使用 Iceberg

`ml/evaluate.py` 中有一个值得注意的设计：

```python
def run_experiment_set(minio_client, mlflow_tracking_uri, bucket, trino_url=None):
    resolved_trino = trino_url or os.environ.get("TRINO_URL")
    if resolved_trino:
        df = _gold_dataframe_from_trino(resolved_trino)  # 走 Iceberg
    else:
        df = _gold_dataframe_from_minio_parquet(minio_client, bucket)  # 走 Parquet
```

当 Trino 可用时，优先从 `iceberg.gold.ecb_dax_features_iceberg` 读取数据；当 Trino 不可用时（如纯单元测试环境），回退到直接读取 MinIO Parquet 文件。这种双通道设计既展示了 Iceberg 的实际使用，又保证了在开发环境中不依赖运行中的 Trino 也能测试 ML 代码。

---

## 12. 机器学习层：MLflow 驱动的实验治理

### 12.1 MLflow 在平台中的定位

MLflow 在 SoloLakehouse 中扮演两个角色：

1. **实验跟踪（Experiment Tracking）**：记录每次模型训练的超参数、评估指标
2. **模型注册（Model Registry）**：将训练好的模型序列化后存储到 MinIO

这使得每次模型训练都是**可复现、可审计、可比较**的，这是从数据工程走向 ML 工程的关键一步。

### 12.2 时间序列交叉验证的重要性

```python
def train(df: pd.DataFrame, model_type: str, params: dict) -> tuple:
    features = [
        "rate_change_bps", "rate_level_pct", "is_rate_hike",
        "is_rate_cut", "dax_volatility_pre_5d", "dax_pre_close"
    ]
    target = "dax_return_1d"  # 实际上是 dax_return_1d > 0 的二值化

    X = df[features]
    y = (df[target] > 0).astype(int)

    tscv = TimeSeriesSplit(n_splits=5)

    all_metrics = {"accuracy": [], "precision": [], "recall": [], "f1": []}

    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = build_model(model_type, params)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_val)

        # 计算指标
        ...

    return model, averaged_metrics
```

**为什么使用 TimeSeriesSplit 而不是随机 K-Fold？**

这是数据工程中一个非常容易犯的错误。对于时间序列数据，随机分割训练集和验证集会导致**前视偏差（look-ahead bias）**：模型在训练时"看到"了时间上在验证集之后的数据，从而在回测中表现虚高，在真实部署中表现差。

`TimeSeriesSplit` 确保验证集的时间永远在训练集之后，模拟了真实的预测场景。这是金融 ML 领域的基本要求，SoloLakehouse 通过明确使用 `TimeSeriesSplit` 展示了这一最佳实践。

### 12.3 超参数搜索的实现

```python
for model_type in ["xgboost", "lightgbm"]:
    for n_estimators in [50, 100, 200]:
        for max_depth in [3, 5]:
            params = {"n_estimators": n_estimators, "max_depth": max_depth}
            with mlflow.start_run() as run:
                model, metrics = train(df=df, model_type=model_type, params=params)

                mlflow.log_param("model_type", model_type)
                mlflow.log_param("n_estimators", n_estimators)
                mlflow.log_param("max_depth", max_depth)
                mlflow.log_metrics({
                    "accuracy": metrics["accuracy"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                })

                # 保存模型制品
                with tempfile.TemporaryDirectory() as tmpdir:
                    model_path = Path(tmpdir) / "model.pkl"
                    model_path.write_bytes(pickle.dumps(model))
                    mlflow.log_artifact(str(model_path), artifact_path="model")
```

这段代码产生 `2 × 3 × 2 = 12` 个 MLflow runs，每个 run 记录了：
- 超参数（model_type, n_estimators, max_depth）
- 评估指标（accuracy, precision, recall, f1）
- 序列化的模型文件（存储在 MinIO `mlflow-artifacts` bucket 中）

在 MLflow UI（http://localhost:5000）中，用户可以在 `ecb_dax_impact` 实验下比较这 12 次运行的结果，按任意指标排序，查看最优模型的超参数组合。

### 12.4 MLflow 的存储架构

MLflow 使用了双存储后端：

- **PostgreSQL `mlflow` 数据库**：存储实验定义、run ID、参数、指标（结构化数据）
- **MinIO `mlflow-artifacts` bucket**：存储模型文件、图表等二进制制品

这种分离的好处是：轻量级的元数据查询通过 SQL 完成，重量级的文件通过 S3 API 完成，各自使用最适合的存储系统。

---

## 13. 编排层：Dagster 软件定义资产的全貌

### 13.1 从脚本到资产图

v1 的管道是一个线性 Python 脚本：

```python
# scripts/run-pipeline.py (v1)
def main():
    step_1_ecb_ingestion()
    step_2_dax_ingestion()
    step_3_ecb_bronze_to_silver()
    step_4_dax_bronze_to_silver()
    step_5_silver_to_gold()
    step_6_ml_experiment()
```

这种方式的问题：
- **没有可视性**：不知道哪个步骤在运行，步骤之间的边界模糊
- **失败不可重试**：如果步骤 5 失败，必须从头重跑或手动跳过前4步
- **没有历史记录**：跑完就消失，无法查看历史运行
- **没有自动化**：需要手动触发，无法按计划自动运行

v2 的 Dagster 软件定义资产（Software-Defined Assets，SDA）范式从根本上改变了这一状况。

### 13.2 资产的核心概念

在 Dagster 中，"资产"（asset）是一个**有名字、有依赖关系、有物化历史**的数据对象。对比传统任务调度的区别：

| 维度 | 传统任务调度（如 Airflow DAG） | Dagster SDA |
|------|-------------------------------|-------------|
| 关注点 | "运行这个任务" | "生成这个数据资产" |
| 依赖关系 | 任务 A 依赖任务 B | 资产 X 依赖资产 Y |
| 重跑单元 | 任务 | 资产（Dagster 自动解析上游依赖） |
| 可观测性 | 任务运行状态 | 数据资产的上次物化时间、行数、路径 |

### 13.3 六个资产的完整实现

```python
# dagster/assets.py

@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def ecb_bronze(context, minio: MinioResource, pipeline_config: PipelineConfigResource):
    started = time.perf_counter()
    result = ECBCollector(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        force=False,
    ).collect()
    context.add_output_metadata({
        "status": result.get("status", "ok"),
        "valid_count": int(result.get("valid_count", 0)),
        "rejected_count": int(result.get("rejected_count", 0)),
        "partition_date": date.today().isoformat(),
        "path": result.get("path", ""),
    })
    _emit_metric("ecb_bronze", started)
    return result
```

注意几个关键设计：

**资产分组**：`group_name="bronze"` 在 Dagster UI 中将 `ecb_bronze` 和 `dax_bronze` 归为一组，使得图可视化更清晰。

**资源注入**：`minio: MinioResource` 和 `pipeline_config: PipelineConfigResource` 通过依赖注入提供。在测试中，可以提供模拟资源；在生产中，提供真实资源。

**输出元数据**：`context.add_output_metadata(...)` 将每次物化的关键指标记录到 Dagster 的持久化存储中。在 Dagster UI 中，可以查看任意历史运行的元数据。

**重试策略**：`RetryPolicy(max_retries=3, delay=5)` 在 Bronze 层（网络 I/O 最多）设置自动重试，Silver/Gold 层不设置（纯计算，失败即异常）。

**依赖声明**：

```python
@asset(group_name="silver")
def ecb_silver(
    context,
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    ecb_bronze: dict[str, Any],  # ← 这里声明依赖 ecb_bronze
) -> str:
    _ = ecb_bronze  # 仅用于声明依赖，不使用其值
    ...
```

通过函数参数声明依赖是 Dagster SDA 的核心模式。`ecb_silver` 接受 `ecb_bronze` 作为参数，Dagster 自动推断出 `ecb_silver` 依赖于 `ecb_bronze`，必须先物化 `ecb_bronze` 才能物化 `ecb_silver`。

### 13.4 性能监控：pipeline_metric

```python
def _emit_metric(step: str, started_at: float) -> None:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info("pipeline_metric",
                metric="pipeline.step.duration_ms",
                step=step,
                value=duration_ms)
```

每个资产物化完成后，都会通过 structlog 记录步骤耗时。这些指标以结构化日志的形式输出，可以被日志聚合系统（如 Loki、ELK）解析，为 v3 的 SLO 监控奠定基础。

---

## 14. 调度、传感器与资产检查：平台自动化的三根支柱

### 14.1 调度（Schedule）

```python
# dagster/definitions.py
from dagster import ScheduleDefinition

daily_pipeline_schedule = ScheduleDefinition(
    job=full_pipeline_job,
    cron_schedule="0 6 * * 1-5",  # 周一至周五 UTC 06:00
    name="daily_pipeline_schedule",
)
```

`0 6 * * 1-5` 是一个精心选择的时间：
- UTC 06:00 对应欧洲夏令时 08:00，大多数欧洲市场刚开盘
- 工作日（周一至周五）跳过周末，因为 ECB 不在周末发布数据

Dagster daemon 服务负责在后台持续评估 cron 表达式，在满足条件时自动提交 run。**调度默认关闭**——用户需要在 Dagster UI 中手动启用，这是对新用户友好的设计，防止自动触发意外运行。

### 14.2 传感器（Sensor）

传感器是 Dagster 中比调度更灵活的自动化机制。调度基于时间触发，传感器基于**条件**触发：

```python
@sensor(job_name="full_pipeline_job", minimum_interval_seconds=1800)
def ecb_data_freshness_sensor(
    minio: MinioResource,
    pipeline_config: PipelineConfigResource
):
    latest = _latest_partition_date(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        prefix="bronze/ecb_rates/",
    )

    if latest is None:
        return RunRequest(
            run_key=f"ecb-freshness-init-{datetime.now(timezone.utc).isoformat()}",
            asset_selection=[AssetKey("ecb_bronze")],
        )

    lag_hours = (datetime.now(timezone.utc).date() - latest).days * 24
    if lag_hours >= 48:
        return RunRequest(
            run_key=f"ecb-freshness-{latest.isoformat()}",
            asset_selection=[AssetKey("ecb_bronze")],
        )
    return SkipReason(
        f"ECB data fresh enough: latest partition {latest.isoformat()} ({lag_hours}h lag)"
    )
```

这个传感器每 30 分钟（`minimum_interval_seconds=1800`）检查一次 ECB Bronze 分区的最新日期。如果数据超过 48 小时没有更新，则发出 `RunRequest` 触发 `ecb_bronze` 资产的重新物化。

**`run_key` 的幂等性设计**：`run_key` 是传感器触发 run 的唯一标识。如果传感器在 30 分钟内多次被评估，并且条件一直满足，Dagster 会使用相同的 `run_key`（因为 `latest.isoformat()` 没有变化）防止重复创建 run。这是传感器实现幂等性的标准模式。

### 14.3 资产检查（Asset Check）

```python
@asset_check(
    asset=gold_features,
    description="gold_features should contain at least 10 rows"
)
def gold_features_min_rows_check(
    minio: MinioResource,
    pipeline_config: PipelineConfigResource,
    gold_features: str,
) -> AssetCheckResult:
    gold_df = _read_parquet_from_minio(
        minio_client=minio.get_client(),
        bucket=pipeline_config.bucket,
        path=gold_features,
    )
    row_count = int(len(gold_df.index))
    passed = row_count >= 10
    return AssetCheckResult(
        passed=passed,
        description=(
            "gold_features has enough event rows for event-study modeling"
            if passed
            else "gold_features has fewer than 10 rows"
        ),
        metadata={"row_count": row_count},
    )
```

资产检查在每次 `gold_features` 资产物化后自动运行。10 行的阈值并不是任意设置的：

- Gold 层每行代表一次 ECB 利率决议事件
- 1999 年至今 ECB 共有约 50+ 次利率变动事件
- 如果只有不到 10 行，说明上游数据有严重问题（可能只摄入了近期数据，或者特征工程筛选过于严苛）
- 少于 10 个样本也无法进行有意义的 TimeSeriesSplit 交叉验证

资产检查的结果在 Dagster UI 中显示为绿色（通过）或红色（失败），并永久保存在 Dagster 的 PostgreSQL 存储中，提供了数据质量的历史审计轨迹。

### 14.4 v1 vs v2 的完整对比

| 维度 | v1 线性脚本 | v2 Dagster |
|------|-----------|------------|
| 触发方式 | `make pipeline-v1` | `make pipeline` / 定时调度 / 传感器 |
| 执行视图 | 控制台日志 | 可视化资产图 + 结构化运行日志 |
| 失败恢复 | 从头重跑 | 单独重新物化失败资产 |
| 历史记录 | 无（日志文件） | PostgreSQL 持久化运行历史 |
| 数据质量 | 脚本内部 `raise` 语句 | 独立资产检查，有状态、可追溯 |
| 调度 | 手动（cron job 外部） | 内置调度，UI 可控 |
| 数据感知 | 无 | 传感器驱动的数据新鲜度检测 |
| 输出元数据 | print/log | 持久化的结构化元数据 |
| 最适合场景 | 快速本地验证、故障降级 | 日常运营、治理演示 |

---

## 15. 可选扩展栈：OpenMetadata 与 Apache Superset

### 15.1 OpenMetadata：数据目录（可选）

OpenMetadata 是一个开源的统一元数据平台，提供数据目录、数据血缘、数据质量和协作功能。在 SoloLakehouse 中，它通过 Docker Compose profile 方式提供：

```bash
make up-openmetadata  # 启动 OpenMetadata + Elasticsearch + MySQL
# http://localhost:8585
```

**为什么是可选的？**

这是一个值得解释的设计决策。OpenMetadata 需要额外的 3 个容器（OpenMetadata Server、Elasticsearch、MySQL），内存需求显著增加。对于只想学习湖仓管道本身的用户，强制包含 OpenMetadata 会增加不必要的复杂度。

通过 Docker Compose profile 将其作为可选扩展，用户可以在了解核心平台之后，再选择性地探索元数据治理能力。这与 v3 的方向一致——数据目录不是所有平台必须的，而是数据治理成熟度到一定阶段后的自然选择。

### 15.2 Apache Superset：BI 探索（可选）

```bash
make up-superset  # 启动 Superset
# http://localhost:8088，默认账密 admin/admin
```

`make up-superset` 自动预配置两个 Trino 数据库连接：

- **`trino_iceberg_gold`** → `trino://sololakehouse@trino:8080/iceberg/gold`
- **`trino_hive_default`** → `trino://sololakehouse@trino:8080/hive/default`

用户启动 Superset 后，无需任何手动配置，直接可以在 SQL Lab 中查询 Iceberg Gold 表，或用 Chart Builder 创建可视化。

这一预配置通过 `docker/superset/bootstrap.sh` 脚本在 Superset 容器启动时自动执行，展示了如何用脚本化方式初始化 BI 工具连接——这在企业环境中是一个常见需求。

---

## 16. 测试策略：无 Docker 单元测试与集成测试分层

### 16.1 测试分层设计

SoloLakehouse 的测试策略遵循测试金字塔原则：

```
        ┌─────────────────┐
        │  集成测试        │ 少量，需要 Docker，覆盖关键路径
        ├─────────────────┤
        │  单元测试        │ 大量，无需 Docker，覆盖所有业务逻辑
        └─────────────────┘
```

### 16.2 单元测试：无 Docker 运行

所有单元测试（`tests/test_*.py`）设计为**不依赖任何运行中的服务**。MinIO、Trino、MLflow 全部通过 `unittest.mock.MagicMock` 模拟。

测试辅助函数（test fixture helpers）的设计是代码质量的体现：

```python
def make_ecb_bronze():
    """创建标准 ECB Bronze 测试 DataFrame"""
    return pd.DataFrame({
        "observation_date": ["2020-01-01", "2020-03-15", "2020-07-01"],
        "rate_pct": [0.0, -0.5, 0.0],
        "_ingestion_timestamp": [datetime.now(UTC)] * 3,
        "_source": ["ECB_SDW"] * 3,
    })
```

使用具名辅助函数而不是在每个测试中重复创建 DataFrame，这既减少了代码重复，也使得测试意图更清晰。

### 16.3 转换函数的纯函数测试

`test_transformation_runs.py` 中对纯转换函数的测试展示了良好的测试设计：

```python
class TestECBBronzeToSilver:
    def test_forward_fill(self):
        """验证前向填充逻辑"""
        df = pd.DataFrame({
            "observation_date": ["2020-01-01", "2020-01-02", "2020-01-03"],
            "rate_pct": [0.0, None, None],  # 后两天无数据
            "_ingestion_timestamp": [datetime.now(UTC)] * 3,
            "_source": ["ECB_SDW"] * 3,
        })
        result = transform_ecb_bronze_to_silver(df)
        assert result["rate_pct"].tolist() == [0.0, 0.0, 0.0]

    def test_rate_change_bps_calculation(self):
        """验证 basis points 计算"""
        df = make_ecb_bronze_with_rates([0.0, 0.25, 0.5])
        result = transform_ecb_bronze_to_silver(df)
        # 从 0.0% → 0.25% = +25 bps
        assert result.iloc[1]["rate_change_bps"] == pytest.approx(25.0)
```

这些测试的特点是：
- **每个测试只验证一个行为**（单一职责原则）
- **测试边界情况**（空值、None 值、序列边界）
- **使用 `pytest.approx`** 进行浮点数比较，避免精度陷阱

### 16.4 Schema 验证测试

```python
class TestECBRecord:
    def test_valid_record(self):
        record = ECBRecord(observation_date="2024-01-15", rate_pct=4.5)
        assert record.rate_pct == 4.5

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ECBRecord(observation_date="2099-01-01", rate_pct=4.5)
        assert "must not be in the future" in str(exc_info.value)

    def test_rate_out_of_range(self):
        with pytest.raises(ValidationError):
            ECBRecord(observation_date="2024-01-15", rate_pct=25.0)  # > 20.0
```

### 16.5 集成测试（需要 Docker）

`tests/integration/` 中的集成测试需要真实服务运行，用 `@pytest.mark.integration` 标记：

```python
@pytest.mark.integration
def test_full_pipeline_smoke():
    """全链路冒烟测试：从摄入到 Gold 注册"""
    ...

@pytest.mark.integration
def test_trino_iceberg_roundtrip():
    """验证 Iceberg 表可以通过 Trino 读写"""
    ...
```

集成测试在 CI 中单独运行（`pytest -m integration`），不在开发时的 `make test`（`pytest -m "not integration"`）中执行。

---

## 17. 配置管理：环境变量、模板与安全边界

### 17.1 三层配置策略

SoloLakehouse 使用了三层配置管理：

**层 1：`.env` 文件**（本地开发）
```bash
MINIO_ROOT_USER=sololakehouse
MINIO_ROOT_PASSWORD=sololakehouse123
S3_ACCESS_KEY=sololakehouse
S3_SECRET_KEY=sololakehouse123
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
TRINO_URL=http://localhost:8080
MLFLOW_TRACKING_URI=http://localhost:5000
```

`.env.example` 包含所有必须变量的示例值，`.env` 被 `.gitignore` 忽略（不提交到版本控制）。

**层 2：Docker Compose `environment:` 注入**
```yaml
services:
  trino:
    environment:
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
```

Docker Compose 自动读取 `.env` 文件并将变量注入容器环境。

**层 3：Trino 模板展开**（`scripts/trino-entrypoint.sh`）

```bash
#!/bin/bash
for template in /etc/trino/catalog-template/*.properties; do
    filename=$(basename "$template")
    eval "echo \"$(cat $template)\"" > /etc/trino/catalog/$filename
done
exec /usr/lib/trino/bin/run-trino
```

注意这里使用 `eval` 而不是 `envsubst`——这是因为 `eval "echo \"$(cat $file)\""` 支持 bash 的所有变量展开语法，而 `envsubst` 只支持简单的 `$VAR` 替换。在配置文件中只用简单变量的情况下，两者等效。

### 17.2 Python 代码中的配置读取

Python 代码使用 `os.environ.get()` 加默认值的模式：

```python
endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
user = os.environ.get("MINIO_ROOT_USER", "sololakehouse")
```

默认值指向 `localhost`——这是一个关键的工程决策。在本地开发（不在 Docker 网络内）时使用 `localhost`；在 Docker Compose 网络内，环境变量会覆盖为容器内部地址（如 `minio:9000`）。

### 17.3 Dagster 资源的配置封装

```python
# dagster/resources.py
class MinioResource(ConfigurableResource):
    endpoint: str = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key: str = os.environ.get("MINIO_ROOT_USER", "sololakehouse")
    secret_key: str = os.environ.get("MINIO_ROOT_PASSWORD", "sololakehouse123")

    def get_client(self):
        return Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False,
        )

class PipelineConfigResource(ConfigurableResource):
    bucket: str = "sololakehouse"
    trino_url: str = os.environ.get("TRINO_URL", "http://localhost:8080")
    mlflow_tracking_uri: str = os.environ.get(
        "MLFLOW_TRACKING_URI", "http://localhost:5000"
    )
```

将配置封装为 Dagster `ConfigurableResource` 有几个好处：
1. 配置逻辑集中在一处，不散落在各个资产函数中
2. 在测试中可以通过依赖注入替换为模拟资源
3. Dagster 可以在 UI 中显示资源配置，增加可观测性

---

## 18. 架构决策记录：每个技术选型的推理链

ADR（Architecture Decision Record）是 SoloLakehouse 中记录技术选型理由的机制。每个重大决策都有一个独立的 ADR 文档，记录背景、决策选项、最终选择和理由。

### 18.1 ADR-001：Docker Compose vs Kubernetes

**决策**：使用 Docker Compose

**核心理由**：
- v1/v2 是单节点参考实现，没有 HA（高可用）需求
- Kubernetes 的学习成本会分散对数据工程核心概念的注意力
- Docker Compose 让平台在任何有 Docker 的笔记本上 5 分钟内可运行
- 升级路径明确：v3 将引入 Kubernetes/Helm/Terraform

**明确的反对意见处理**：
> "但 Docker Compose 不是生产级别的！"

这是正确的。SoloLakehouse 明确将生产化定为 v3 目标，v1/v2 是参考实现而非生产部署方案。

### 18.2 ADR-002：Trino vs DuckDB

**决策**：使用 Trino

这是一个不那么显而易见的选择。DuckDB 更轻量、性能更好（对于单机场景）、Python 集成更简单。为什么选择 Trino？

**关键理由**：
1. **多 Catalog 联邦**：Trino 原生支持同时连接 Hive 和 Iceberg catalog，DuckDB 没有等效能力
2. **Hive Metastore 集成**：展示完整的 Hive Metastore + 外部表模式，这是企业数据平台的标准组件
3. **分布式潜力**：Trino 可以水平扩展到多 worker 集群，DuckDB 是单进程
4. **SQL 方言兼容性**：Trino 的 SQL 方言与 Presto（AWS Athena 的基础）高度兼容

DuckDB 的适用性更适合纯本地分析场景，而 Trino 更符合 "演示企业湖仓内部机制" 的目标。

### 18.3 ADR-003：Parquet vs Delta Lake

**决策**：Bronze/Silver 使用 Parquet，Gold 使用 Iceberg

**理由**：
- v1/v2 的 Bronze 层是追加-only 写入，不需要 ACID 事务
- Parquet 比 Delta Lake 或 Iceberg 更简单，减少了新用户的学习曲线
- Gold 层（v2.5）引入 Iceberg 是有意识的升级路径演示：当场景需要（事务性、时间旅行）时才引入更复杂的表格式
- 这种分层使用（Bronze/Silver 用 Parquet，Gold 用 Iceberg）实际上更接近许多企业的真实实践

### 18.4 ADR-004：ECB + DAX 数据集

**决策**：使用 ECB 利率 API + DAX 样本 CSV

**关键约束满足**：
- 完全公开，无 API Key
- 时序结构，适合演示时序工程技术
- 两个可关联的独立来源，支持 Join 和特征工程
- 数据量适中（ECB ~800 条记录，DAX ~1300 条记录）
- 真实业务假设（利率对股市的影响）

### 18.5 ADR-006：Dagster 编排 + 遗留脚本兼容路径

**决策**：默认使用 Dagster，保留 v1 脚本作为永久兼容路径

**理由**：
- 渐进式迁移：不强迫用户一步切换到 Dagster
- 故障降级：如果 Dagster 不可用（如容器问题），`make pipeline-v1` 仍然工作
- 学习路径：用户可以先理解 v1 的线性逻辑，再理解 v2 的资产图

这一决策体现了一个重要的工程原则：**新架构不应该破坏旧的工作方式，直到新架构足够成熟和可靠**。

### 18.6 ADR-013：Iceberg Gold via Trino

**决策**：通过 Trino CTAS 从 Hive 外部表创建 Iceberg 表

**为什么不直接写 Iceberg 而不写 Parquet？**

1. **避免上游管道修改**：如果直接写 Iceberg，需要修改 Python 写入代码，引入 Iceberg 写入库
2. **Hive 外部表保持向后兼容**：已有的基于 Hive catalog 的查询不需要改变
3. **Trino 作为格式转换中间层**：Trino 的 CTAS 能力使得格式升级与数据管道解耦

### 18.7 ADR-014：OpenMetadata 可选 Profile

**决策**：OpenMetadata 通过 Docker Compose profile 可选启用

**理由**：
- 不是所有用户都需要完整的数据目录
- OpenMetadata 增加约 2GB 内存需求
- 可选扩展允许用户按需探索元数据治理
- v3 的 "企业目录迁移" 也是可选的（不强制要求）

---

## 19. 版本演进叙事：v1 → v2 → v3 的设计哲学

### 19.1 版本叙事框架

SoloLakehouse 的每个版本都有一个中心问题：

> **v1 回答：** 湖仓管道能否端到端运行、被验证，并支持最小化的数据到 ML 循环？
> **v2 回答：** 这个管道能否作为一个平台来运营，具备资产编排、调度、检查和回放能力？
> **v3 回答：** 这个平台能否通过多环境部署、治理、安全、可观测性和发布控制被生产化加固？

每个版本不是前一个版本的简单扩展，而是回答了一个**本质上更难的问题**。

### 19.2 v1：证明核心可行性

v1 的核心成就是将五层服务集成为一个可一键运行的平台。这听起来简单，但实际工程挑战不小：

- Hive Metastore 需要等待 PostgreSQL 完全就绪才能启动
- Trino 需要等待 Hive Metastore 完全就绪才能加载 catalog
- MLflow 的 artifact 存储需要 MinIO bucket 预先存在
- 所有服务的凭据需要通过环境变量一致传递

v1 解决了所有这些启动顺序和配置协调问题，使得 `make up && make pipeline` 成为一个真实可用的一键部署流程。

### 20.2 v1 → v2 的核心跃升

v1 证明了数据管道能运行。v2 的核心问题是：**一个真实的数据平台需要什么额外能力？**

答案是：**可观测性、调度自动化、失败恢复、数据质量治理**。

v2 引入的 Dagster 层没有替换任何数据逻辑，而是在数据逻辑之上建立了一套**平台运营基础设施**：

1. **可观测性**：每次运行的状态、持续时间、行数都持久化在数据库中，可以通过 UI 查询
2. **调度自动化**：不需要手动运行，平台按计划自动刷新数据
3. **失败恢复**：Dagster 的资产粒度重试让失败恢复从 "重跑全部" 变为 "重跑失败的那一步"
4. **数据质量治理**：资产检查将 "数据正确性" 从代码注释变成了可追溯的平台级质量门禁

### 19.3 v2 中的保守主义哲学

v2 中有几个刻意保守的设计选择：

**保留 v1 兼容路径**：`make pipeline-v1` 永远可用，这不是临时措施，而是架构设计。Dagster 的新依赖（额外的 2 个容器）可能在某些环境中出现问题，v1 脚本提供了一个始终可用的降级选项。

**Dagster 不重写数据逻辑**：如果 Dagster 的 API 发生变化或者项目迁移到不同的编排系统，数据逻辑（`ingestion/`、`transformations/`、`ml/`）完全不受影响。这是**关注点分离**在架构层面的体现。

**v2.5 的 Iceberg 和 OpenMetadata 是可选的**：这些 v2.5 特性演示了 "下一步可以做什么"，但不是 v2 运营的必要条件。将它们设计为可选，防止了过早的复杂性增加。

### 19.4 v3 的定位：生产化 vs 特性扩展

v3 的规划文档明确区分了**生产化（productionization）**和**特性扩展（feature expansion）**，并明确 v3 只做前者：

**v3 的生产化优先级**：
1. **基础设施**：Kubernetes + Helm + Terraform（多环境、可重复部署）
2. **运营模型**：`dev → staging → production` 环境晋升链
3. **安全治理**：Secrets 生命周期管理（替代静态 `.env`）、最小权限访问
4. **可靠性/可观测性**：SLO 定义、指标仪表板、告警规则、事故处理手册
5. **数据治理基线**：Gold 层和关键 Silver 层的治理合约（数据所有者、刷新 SLA）
6. **ML 治理**：可复现的训练/评估合约，制品血缘

**v3 明确排除的内容**：
- Kafka/Flink 流处理扩展
- 强制迁移到 OpenMetadata/DataHub
- 全量改用 Delta Lake / Iceberg（Bronze/Silver 继续用 Parquet）
- 在线模型服务平台
- Superset/FastAPI 作为必要交付物

这种明确的范围界定（scope guardrails）是项目规划成熟度的体现。知道什么 **不做** 与知道什么 **做** 同样重要。

---

## 20. 生产就绪性评估与 v3 展望

### 20.1 v2 的能力上限

SoloLakehouse v2 当前适合的场景：

| 场景 | 适合 |
|------|------|
| 小型内部数据团队的 MVP 平台 | ✅ |
| 中低频批处理工作负载（每日一次） | ✅ |
| 数据工程概念学习和演示 | ✅ |
| 企业合规要求的生产平台 | ❌ |
| 多团队、多租户数据平台 | ❌ |
| 需要 HA（高可用）的关键业务系统 | ❌ |
| 近实时数据处理（< 1小时延迟） | ❌ |

### 20.2 已知的生产就绪缺口

**安全**：
- `.env` 文件中的明文凭据不适合生产（需要 Vault/AWS Secrets Manager）
- 所有服务之间没有 mTLS（生产需要服务间加密通信）
- Dagster UI 和 Trino 没有身份认证（生产需要 SSO/LDAP 集成）

**可观测性**：
- 目前只有 structlog 记录的应用日志，没有指标聚合
- 没有 Prometheus + Grafana（ADR-005 明确推迟到 v3）
- 没有告警规则和 SLO 定义
- 没有分布式链路追踪（Jaeger/Zipkin）

**可靠性**：
- 所有服务在单节点 Docker Compose 上运行，单点故障
- 没有数据备份机制（MinIO 数据丢失 = 全部数据丢失）
- 没有灾难恢复计划（DR）

**发布管理**：
- 没有环境晋升流程（直接部署到 "生产"）
- 没有金丝雀发布或蓝绿部署
- 没有数据管道版本化和回滚机制

### 20.3 v3 架构方向

v3 的技术栈升级方向（基于 roadmap.md 和 EVOLVING_PLAN.md）：

```
v2 (当前)                    v3 (规划)
─────────────────────────────────────────────
Docker Compose        →  Kubernetes + Helm
手动 make up          →  Terraform 自动化部署
.env 文件凭据         →  HashiCorp Vault / AWS SM
单环境               →  dev/staging/production 三环境
无指标监控            →  Prometheus + Grafana + Alertmanager
无 SLO 定义          →  定义 SLO，建立 SLA 合约
手动发布              →  CI/CD 环境晋升 pipeline
无数据治理合约        →  Hive-first 数据所有者 / 刷新 SLA 元数据
```

---

## 21. 快速上手指南

### 21.1 前置条件

| 软件 | 版本要求 | 验证命令 |
|------|---------|---------|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | v2.20+ (插件模式) | `docker compose version` |
| Python | 3.13+ | `python3 --version` |
| GNU Make | 任意 | `make --version` |
| 可用内存 | ≥ 4 GB（推荐 8 GB） | — |
| 可用磁盘 | ≥ 5 GB | — |

### 21.2 五步启动

```bash
# 步骤 1：克隆仓库
git clone <repository-url>
cd SoloLakehouse

# 步骤 2：创建 Python 虚拟环境
python3 -m venv .venv && source .venv/bin/activate

# 步骤 3：安装 Python 依赖
pip install -r requirements.txt

# 步骤 4：一键启动（第一次运行，拉镜像需要 5-10 分钟）
make setup  # 检查 Docker → 确保 .env 存在 → 拉镜像 → 启动 → 等待健康检查

# 步骤 5：验证平台健康
make verify
```

期望输出：

```
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS    Buckets: sololakehouse, mlflow-artifacts
PostgreSQL       PASS    Databases: dagster_storage, hive_metastore, mlflow
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200
Dagster          PASS    HTTP 200 /server_info
```

### 21.3 运行管道

```bash
# v2 默认路径（Dagster）
make pipeline

# v1 兼容路径（线性脚本）
make pipeline-v1

# 强制重新摄入（忽略增量检查）
make pipeline ARGS="--force"
```

### 21.4 探索各组件 UI

| 组件 | URL | 默认凭据 |
|------|-----|---------|
| MinIO Console | http://localhost:9001 | `sololakehouse` / `sololakehouse123` |
| Trino UI | http://localhost:8080 | 无（只读） |
| MLflow UI | http://localhost:5000 | 无 |
| Dagster UI | http://localhost:3000 | 无 |
| Superset (可选) | http://localhost:8088 | `admin` / `admin` |
| OpenMetadata (可选) | http://localhost:8585 | `admin@open-metadata.org` / `Admin1234!` |

### 21.5 关键 Trino SQL 演示

进入 Trino CLI：

```bash
docker exec -it slh-trino trino
```

查询 Gold 层特征表：

```sql
-- 列出所有可用 catalog
SHOW CATALOGS;

-- 列出 Hive catalog 中的 schema
SHOW SCHEMAS IN hive;

-- 查询 Gold 层事件研究特征
SELECT
    event_date,
    rate_change_bps,
    CASE WHEN is_rate_hike THEN '加息' ELSE '降息' END AS direction,
    ROUND(dax_return_1d, 2) AS dax_next_day_return,
    ROUND(dax_return_5d, 2) AS dax_5day_cumulative_return
FROM hive.gold.ecb_dax_features
ORDER BY event_date;

-- 通过 Iceberg catalog 查询（v2.5）
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 5;

-- 分析加息 vs 降息后的平均 DAX 表现
SELECT
    CASE WHEN is_rate_hike THEN 'Rate Hike' ELSE 'Rate Cut' END AS event_type,
    COUNT(*) AS event_count,
    ROUND(AVG(dax_return_1d), 2) AS avg_1d_return,
    ROUND(AVG(dax_return_5d), 2) AS avg_5d_return
FROM hive.gold.ecb_dax_features
GROUP BY is_rate_hike;
```

---

## 22. 总结：这个 Repo 教会我们什么

### 22.1 核心洞见

通过阅读和运行 SoloLakehouse，可以建立对以下概念的真实理解，而不只是 "知道名字"：

**1. 湖仓架构不是一个产品，而是一种架构模式**

Databricks 和 Snowflake 所谓的 "湖仓" 本质上是：对象存储（S3/ADLS/GCS）+ 开放表格式（Delta/Iceberg）+ 计算引擎（Spark/Trino）+ 元数据管理（Hive Metastore/Glue）的组合。SoloLakehouse 用完全开源的组件复现了这一模式，使得每个层次都可以透明审查。

**2. Medallion 模型是工程约定，不是技术限制**

Bronze 的不可变性、Silver 的规范化、Gold 的业务就绪性——这些是工程团队对数据处理阶段的主动设计，而不是工具强制的约束。好的 Medallion 实现需要对每一层的 "这里存什么、为什么存" 有清晰的回答。

**3. 编排是关注点，不是替代**

Dagster 没有替换任何数据逻辑，它只是在数据逻辑之上建立了平台语义。这一区分对于理解为什么 v1 和 v2 产生相同的数据输出但具有本质不同的运营能力至关重要。

**4. 时间序列 ML 有其特定的工程要求**

TimeSeriesSplit 不是可选的最佳实践，而是避免前视偏差的必要条件。Gold 层的特征工程（事件研究窗口）不是任意的，而是来自金融分析的成熟方法论。

**5. 生产就绪是一个独立的工程挑战**

v2 的 "技术上可用" 和 v3 的 "生产就绪" 之间有一条巨大的鸿沟。安全治理、多环境部署、SLO 驱动的可观测性、数据合约——这些不是高级功能，而是生产数据平台的基础要求。SoloLakehouse 通过明确将这些推迟到 v3 并详细记录在路线图和 ADR 中，诚实地承认了这条鸿沟的存在。

### 22.2 代码质量的体现

SoloLakehouse 的代码质量不只体现在逻辑正确性上，更体现在一系列工程习惯：

- **纯函数与编排函数的分离**：转换层的所有函数都有一个无副作用的纯函数版本，独立可测
- **永不静默丢弃数据**：拒绝记录写入 `bronze/rejected/` 而不是被丢弃
- **structlog 的结构化日志**：所有日志都是 key-value 对，而不是格式化字符串，为机器解析友好
- **Pydantic v2 的领域约束**：Schema 验证不只检查类型，还检查业务规则（范围、未来日期等）
- **ADR 文档化**：每个重要的技术选型都有记录，包括被拒绝的方案和理由
- **`.model_dump()` 不是 `.dict()`**：明确使用 Pydantic v2 API，避免 v1/v2 混用

### 22.3 作为学习路径的建议

如果你想从这个 repo 中获得最大价值，建议按以下顺序探索：

1. **阅读 `docs/architecture.md`**：建立整体架构的心智模型
2. **运行 `make setup && make pipeline-v1`**：先理解 v1 线性路径
3. **在 MinIO Console 中浏览数据分层**：理解 Bronze/Silver/Gold 的实际文件结构
4. **在 Trino CLI 中运行示例查询**：感受 SQL 层对 Parquet 文件的抽象
5. **阅读 `ingestion/collectors/ecb_collector.py`**：理解 Collector 模式的完整实现
6. **阅读 `transformations/silver_to_gold_features.py`**：理解事件研究特征工程
7. **运行 `make pipeline`**：体验 v2 Dagster 编排，探索 Dagster UI
8. **阅读 `dagster/assets.py`**：理解软件定义资产如何包装已有逻辑
9. **阅读各 ADR 文档**：理解每个技术选型的推理过程
10. **阅读 `docs/roadmap.md`**：理解版本演进的设计哲学

### 22.4 最后的陈述

SoloLakehouse 最终传递的信息是：**优秀的数据平台工程是可以被理解、被学习、被复现的**。那些在 Databricks 或 Snowflake 上被抽象掉的复杂性，不是魔法，而是可以用开源工具和清晰的工程设计来重现的。

这个 repo 的价值不在于它能处理多大的数据量，而在于它展示了构建现代数据平台所需的**完整思维框架**：从数据源到 ML 实验，从基础设施到可观测性，从单节点参考到生产化路线图。

---

## 附录 A：完整代码逐文件精读

以下对 SoloLakehouse 中最核心的源代码文件进行逐一深度解析，补充正文中未展开的工程细节。

### A.1 `ingestion/bronze_writer.py`：Parquet 写入的基础层

`BronzeWriter` 是整个摄入管道的终点，也是所有数据进入存储层前的最后一道门。它只有两个方法：`write()` 和 `write_rejected()`，简洁的接口背后是一系列精心的工程决策。

**`preserve_index=False` 的重要性**

```python
table = pa.Table.from_pandas(df, preserve_index=False)
```

Pandas DataFrame 在内部维护一个 `RangeIndex`（默认的 0, 1, 2...）或用户自定义的索引。`preserve_index=False` 告诉 PyArrow **不要将 DataFrame 索引序列化为 Parquet 的一个列**。如果不设置这个参数，Parquet 文件中会多出一个 `__index_level_0__` 列，下游的 Trino 和 Spark 读取时会看到这个无意义的列，造成 schema 污染。

在整个代码库中，所有 `pa.Table.from_pandas()` 调用都带有 `preserve_index=False`，这是一个一致的约定。

**`buffer.getbuffer().nbytes` 而不是 `len(buffer.getvalue())`**

```python
self.minio.put_object(
    self.bucket, path, buffer,
    length=buffer.getbuffer().nbytes,
)
```

MinIO 的 `put_object` 需要知道 content length 才能正确发送 HTTP PUT 请求。`buffer.getbuffer().nbytes` 返回 `BytesIO` 内部 buffer 的字节数，这在 `buffer.seek(0)` 之后仍然正确。如果使用 `len(buffer.getvalue())` 会创建一个额外的字节串拷贝，内存效率较低；如果忘记先 `seek(0)` 就调用 `read()`，会返回空字节串。

**`write_rejected` 的防御性检查**

```python
for record in records:
    reason = record.get("rejection_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Each rejected record must include a non-empty rejection_reason")
```

在写拒绝记录之前，代码会验证每条记录都包含非空的 `rejection_reason` 字段。这防止了 "有记录被写入拒绝分区但没有拒绝原因" 的情况——这种情况在数据质量分析时几乎等同于信息丢失。

### A.2 `ingestion/quality/bronze_checks.py`：质量门禁的完整实现

质量检查函数是纯函数（无副作用，只有 DataFrame 输入和异常输出），这使得它们可以在不启动任何外部服务的情况下进行单元测试。

**`check_date_continuity` 的算法**

```python
def check_date_continuity(df: pd.DataFrame, date_col: str, max_gap_days: int) -> None:
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna().sort_values()
    deltas = dates.diff().dropna().dt.days
    if not deltas.empty and int(deltas.max()) > max_gap_days:
        raise ValueError(f"Date gap exceeds {max_gap_days} days in {date_col}")
```

`dates.diff()` 计算相邻日期的差值，`.dt.days` 将时间差转换为整数天数。注意 `dropna()` 两次出现：第一次删除无效日期（`errors="coerce"` 将解析失败的值设为 NaT），第二次删除 diff 后第一行的 NaN（序列差分的第一个元素始终为 NaN）。

`int(deltas.max())` 的 `int()` 转换是必要的——pandas 的 `max()` 对于整数序列可能返回 `numpy.int64`，而 `> max_gap_days` 的比较在某些 Python 版本中对 numpy 整数类型的行为不完全一致。

**ECB 和 DAX 质量套件的差异**

`run_ecb_bronze_checks` 和 `run_dax_bronze_checks` 体现了针对不同数据源的差异化质量规则：

| 检查项 | ECB | DAX |
|--------|-----|-----|
| 空值检查 | `observation_date`, `rate_pct` | 所有价格列和 volume |
| 未来日期 | ✅ | ✅ |
| 日期连续性 | `max_gap_days=180` | `max_gap_days=5` |
| Schema 版本 | 4 列 | 8 列 |

DAX 数据的空值检查更严格（检查所有 OHLCV 列），因为价格数据中的空值通常意味着数据损坏，而 ECB 数据的 `rate_pct` 可能合法地在某些日期缺失（API 特性），这由下游的前向填充处理。

### A.3 `ingestion/trino_sql.py`：跨 HTTP 的 SQL 执行

`trino_sql.py` 直接使用 HTTP REST API 与 Trino 通信，而不是使用 SQLAlchemy 或 Trino Python 客户端库。这个选择有其原因：

**Trino REST API 的轮询模型**

Trino 的查询执行是异步的。`POST /v1/statement` 提交查询后，Trino 返回一个包含 `nextUri` 的响应。客户端需要持续 `GET nextUri` 直到响应中没有 `nextUri`（查询完成）或出现 `error` 字段：

```python
while True:
    if "error" in payload:
        message = payload["error"].get("message", "unknown Trino error")
        raise ValueError(message)
    next_uri = payload.get("nextUri")
    if not next_uri:
        return payload  # 查询完成
    if time.monotonic() > deadline:
        raise TimeoutError("Trino query polling exceeded timeout")
    response = requests.get(next_uri, timeout=30)
    payload = response.json()
```

`deadline = time.monotonic() + poll_timeout_s` 使用单调时钟（monotonic clock）而不是挂钟时间（wall clock），这防止了系统时钟调整（如 NTP 同步）导致的超时计算错误。

**瞬态错误的识别与重试**

```python
def _is_retryable_trino_error(exc: Exception) -> bool:
    message = str(exc).lower()
    transient_markers = (
        "sockettimeoutexception",
        "read timed out",
        "timeout",
        "timed out",
        "hive-metastore",  # HMS 暂时不可用
    )
    return any(marker in message for marker in transient_markers)
```

包含 `"hive-metastore"` 这一关键词是一个实践经验的产物：在 Docker Compose 环境中，Hive Metastore 有时在 Trino 已经启动后仍然在初始化，导致早期的 `CREATE TABLE` 请求失败，错误消息中包含 "hive-metastore"。识别这类瞬态错误并重试，而不是立即失败，是提高平台启动鲁棒性的关键。

**Hive 外部表的 s3:// vs s3a://**

```sql
CREATE TABLE IF NOT EXISTS hive.gold.ecb_dax_features (...)
WITH (
    format = 'PARQUET',
    external_location = 's3://{bucket}/gold/rate_impact_features/'
)
```

注意这里使用 `s3://` 而不是 `s3a://`。Trino 的 Hive connector 默认使用 `s3://` 协议，并通过 `hive.s3.endpoint` 配置将其重定向到 MinIO。如果使用 `s3a://`，则需要通过 Hadoop 配置（`core-site.xml`）映射——在这个简化的 Docker 环境中，`s3://` 更直接。

### A.4 `dagster/definitions.py`：平台注册中心

`definitions.py` 是 Dagster 代码位置（code location）的入口点，它的作用类似于依赖注入框架中的注册中心：

```python
defs = Definitions(
    assets=all_assets,
    asset_checks=[gold_features_min_rows_check],
    jobs=[full_pipeline_job],
    schedules=[daily_pipeline_schedule],
    sensors=[ecb_data_freshness_sensor],
    resources={
        "minio": MinioResource(),
        "pipeline_config": PipelineConfigResource(),
        "parquet_io_manager": ParquetIOManager(),
    },
)
```

**`Definitions` 对象的重要性**

Dagster 1.x 引入了 `Definitions` 作为取代旧式 `repository` 的现代 API。它有几个重要特性：

1. **单一入口**：整个代码位置只有一个 `Definitions` 对象，Dagster webserver 加载这个对象来了解所有可用的资产、作业、调度和传感器。
2. **资源绑定**：`resources` 字典中的键（如 `"minio"`）需要与资产函数参数名完全匹配（`def ecb_bronze(context, minio: MinioResource)`），Dagster 通过名称匹配完成依赖注入。
3. **编译时验证**：Dagster 在加载 `Definitions` 时会进行静态验证，比如检查资产声明的资源键是否在 `resources` 字典中存在，这让配置错误在启动时而不是运行时暴露。

**`ParquetIOManager` 的预留扩展点**

```python
"parquet_io_manager": ParquetIOManager(),
```

`ParquetIOManager` 是一个自定义 IO 管理器，注册在 `defs` 中但默认不用于任何资产。这是一个**预留扩展点**——未来如果某个资产想要通过 IO 管理器自动处理 DataFrame 的读写（而不是手动调用 `minio.put_object`），可以在资产定义上添加 `@asset(io_manager_key="parquet_io_manager")` 而无需修改 `definitions.py`。

### A.5 `ml/train_ecb_dax_model.py`：训练逻辑的细节

**两阶段训练：CV + 最终模型**

```python
# 阶段1：TimeSeriesSplit 交叉验证，收集指标
for train_idx, test_idx in splitter.split(x):
    fold_model = _make_model(model_type=model_type, params=params)
    fold_model.fit(x.iloc[train_idx], y.iloc[train_idx])
    predictions = fold_model.predict(x.iloc[test_idx])
    accuracy_scores.append(float(accuracy_score(...)))

# 阶段2：在全部数据上训练最终模型（用于制品存储）
model = _make_model(model_type=model_type, params=params)
model.fit(x, y)
```

这是 ML 工程中的标准模式：CV 用于**评估**（获得无偏的泛化性能估计），最终训练用全部数据以**最大化信息利用**（因为不需要留出验证集）。CV 的指标用于比较不同超参数组合，最终模型用于实际预测或部署。

**`zero_division=0` 的工程考量**

```python
precision_scores.append(
    float(precision_score(y.iloc[test_idx], predictions, zero_division=0))
)
```

`zero_division=0` 处理了一个边界情况：如果模型在某个 fold 上没有预测任何正类（所有预测都是负类），精确率（precision = TP / (TP + FP)）的分母为 0。设置 `zero_division=0` 时，这种情况返回 0 而不是 `NaN` 或抛出警告。

在 ECB 利率数据这种样本量较小的场景中，这个边界情况是真实可能发生的，尤其是在 `n_splits=5` 的早期折叠（训练数据很少，模型可能倾向于预测多数类）。

**特征中的布尔列转换**

```python
x["is_rate_hike"] = x["is_rate_hike"].astype(int)
x["is_rate_cut"] = x["is_rate_cut"].astype(int)
```

XGBoost 和 LightGBM 都接受布尔类型的特征，但将其显式转换为 int（0/1）是更安全的做法：某些版本的 scikit-learn 兼容接口（如 `.predict`）在处理 pandas 布尔类型时会发出警告或行为不一致。显式转换消除了这种不确定性。

---

## 附录 B：关键设计模式的横切分析

### B.1 "纯函数 + 编排" 分离模式

整个代码库中最一致的设计模式是**纯函数与编排函数的分离**。几乎每个有实际计算逻辑的文件都遵循这个结构：

```
transformations/ecb_bronze_to_silver.py
├── transform_ecb_bronze_to_silver(df) → df     # 纯函数：可测试，无 I/O
└── run(minio_client, bucket) → str              # 编排函数：读 MinIO → 调用纯函数 → 写 MinIO

transformations/dax_bronze_to_silver.py
├── transform_dax_bronze_to_silver(df) → df
└── run(minio_client, bucket) → str

transformations/silver_to_gold_features.py
├── build_gold_features(ecb_df, dax_df) → df
└── run(minio_client, bucket) → str

ml/train_ecb_dax_model.py
├── train(df, model_type, params) → (model, metrics)
└── (evaluate.py 中的 run_experiment_set 作为编排层)
```

这个模式的价值在于：

**测试效率**：单元测试只需要测试纯函数，可以用构造的 DataFrame 作为输入，无需模拟任何 I/O。编排函数通过模拟 `minio_client` 来测试。

**可替换性**：如果存储后端从 MinIO 换成 HDFS 或本地文件系统，只需要修改 `run()` 函数，不需要修改任何业务逻辑。

**可组合性**：纯函数可以在不同上下文中被调用——v1 脚本、v2 Dagster 资产、命令行工具、Jupyter Notebook——它们的行为完全一致。

### B.2 结构化日志约定

代码库全面使用 `structlog` 进行结构化日志记录，以下是所有日志调用遵循的约定：

**事件名称**：`snake_case`，描述发生了什么事件
```python
logger.info("ecb_fetch_started")
logger.info("ecb_validation_complete", valid_count=847, rejected_count=0)
logger.info("ecb_ingestion_complete", valid_count=847, path="bronze/ecb_rates/...")
logger.warning("trino_gold_registration_retry", attempt=1, max_attempts=3)
```

**上下文作为 key-value 对**：所有相关数量、路径、标识符都作为独立的关键字参数传递，而不是格式化字符串
```python
# 好：机器可解析
logger.info("ml_run_complete", run_id="abc123", accuracy=0.75)

# 不好：机器难以解析
logger.info(f"ML run abc123 completed with accuracy 0.75")
```

**在步骤边界记录**：每个逻辑步骤的开始（`_started`）和结束（`_complete`）都有日志条目，配合 `_emit_metric` 记录耗时。

**structlog 的格式无关性**：`structlog` 的事件/key-value 格式在开发环境中可以输出为人类可读的彩色文本，在生产环境中可以配置为 JSON 格式，供 ELK/Loki 等日志聚合系统解析。这个切换不需要修改任何日志调用代码。

### B.3 MinIO I/O 的连接管理模式

代码库中所有从 MinIO 读取数据的地方都使用相同的模式：

```python
response = minio_client.get_object(bucket, path)
try:
    df = pd.read_parquet(BytesIO(response.read()))
finally:
    response.close()
    response.release_conn()
```

`try/finally` 确保无论 `pd.read_parquet` 是否抛出异常，连接都会被正确关闭和释放。`response.close()` 关闭 HTTP 响应体的读取流，`response.release_conn()` 将底层 HTTP 连接归还给连接池。

如果省略这两个调用，长时间运行的管道会积累未关闭的 HTTP 连接，最终导致连接池耗尽。在 v2 的 Dagster 环境中，资产可能在同一进程中被反复触发，连接泄漏的风险更高，这个模式的重要性也更大。

**`_read_parquet_from_minio` 的提取**

在 `dagster/assets.py` 中，这个模式被提取为一个辅助函数：

```python
def _read_parquet_from_minio(minio_client: Any, bucket: str, path: str) -> pd.DataFrame:
    response = minio_client.get_object(bucket, path)
    try:
        return pd.read_parquet(BytesIO(response.read()))
    finally:
        response.close()
        response.release_conn()
```

这个提取减少了重复代码，但更重要的是将 "正确关闭连接" 的责任集中在一处，防止遗漏。

### B.4 Dagster 资产元数据的业务价值

每个 Dagster 资产物化后调用 `context.add_output_metadata(...)` 记录的数据，在实际运营中具有重要价值：

```python
context.add_output_metadata({
    "status": "ok",
    "valid_count": 847,
    "rejected_count": 0,
    "partition_date": "2024-01-15",
    "path": "bronze/ecb_rates/ingestion_date=2024-01-15/ecb_rates.parquet",
    "rejected_path": "",
})
```

**快速定位异常**：如果某天 `valid_count` 突然从 847 降到 0，或 `rejected_count` 突然增加，运营人员无需查看日志就能发现数据质量问题。

**路径可追溯**：`path` 字段直接给出了物化产生的 MinIO 对象路径，方便直接检查原始数据。

**历史趋势**：Dagster 将所有物化的元数据持久化在 PostgreSQL 中，可以查询历史趋势（如过去 30 天的平均 `valid_count`），这是 v3 SLO 监控的数据基础。

---

## 附录 C：运维操作手册

### C.1 日常操作

**启动平台**

```bash
make up          # 服务已存在（第一次之后）
make setup       # 第一次运行（包含 Docker 检查和镜像拉取）
```

**停止平台**

```bash
make down        # 停止服务，保留所有数据（volumes 保留）
make clean       # 停止服务，删除所有 volumes（数据丢失！慎用）
```

**运行管道**

```bash
make pipeline                    # v2 Dagster 路径（推荐）
make pipeline-v1                 # v1 线性脚本（备用）
make pipeline ARGS="--force"     # 强制重新摄入（忽略增量检查）
```

**验证平台健康**

```bash
make verify                      # 检查全部 6 个核心服务
make verify-openmetadata         # 检查 OpenMetadata（如果已启动）
make verify-superset             # 检查 Superset（如果已启动）
```

### C.2 故障诊断流程

**步骤 1：查看哪个服务失败**

```bash
make verify
# 输出示例：
# MinIO            PASS
# PostgreSQL       PASS
# Hive Metastore   FAIL    ← 问题在这里
# Trino            TIMEOUT
```

**步骤 2：查看失败服务的日志**

```bash
docker logs slh-hive-metastore --tail 50
docker logs slh-trino --tail 50
docker logs slh-dagster-webserver --tail 50
```

**步骤 3：常见问题对照**

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| Hive Metastore FAIL | PostgreSQL 未就绪时已启动 | `make clean && make up` |
| Trino "catalog not available" | HMS 仍在初始化 | 等待 60 秒后重试 `make verify` |
| Dagster FAIL | webserver 仍在启动（60s start_period）| 等待 90 秒，或查看 `docker logs slh-dagster-webserver` |
| `pipeline` 返回 "No such container" | Dagster 容器未运行 | `make up && make verify` 后重试 |
| Gold 表查询无行 | Trino 未就绪时注册了表 | `make pipeline` 重新运行 |
| ECB API 超时 | ECB SDW API 偶发性缓慢 | 重试 `make pipeline`；或切换 `make pipeline-v1` 调试 |

**步骤 4：查看容器状态**

```bash
docker compose -f docker/docker-compose.yml ps
# 查看所有容器的状态和健康检查状态
```

### C.3 数据恢复场景

**场景 1：意外运行了 `make clean`**

`make clean` 删除所有 Docker volumes，包括 MinIO 数据、PostgreSQL 数据和 Dagster 历史。数据无法从 Docker 层面恢复。解决方案：重新运行 `make setup && make pipeline` 从 ECB API 和 DAX 样本 CSV 重新生成所有数据。

**场景 2：Silver 层数据损坏**

Bronze 层不可变，重新运行 Silver 转换即可恢复：

```bash
# 在 v1 模式下可以跳过 Bronze 步骤
make pipeline-v1 ARGS="--skip-bronze"
# 或在 Dagster UI 中单独重新物化 ecb_silver 和 dax_silver
```

**场景 3：Gold 层需要重新注册 Trino 表**

如果 Hive Metastore 或 Trino 重置，表定义会丢失，但 Gold Parquet 文件仍然存在。只需重新运行 Gold 层物化或调用：

```bash
make pipeline  # 重跑全部，Gold 资产会重新注册 Trino 表
```

### C.4 扩展管道：添加新数据源

遵循 Collector 模式，添加新数据源只需三步：

**步骤 1：创建 Schema**

```python
# ingestion/schema/new_source_schema.py
from pydantic import BaseModel, field_validator

class NewSourceRecord(BaseModel):
    observation_date: dt.date
    value: float
    # ... 其他字段

    @field_validator("value")
    @classmethod
    def validate_value_range(cls, v: float) -> float:
        if not 0 <= v <= 1000:
            raise ValueError("value out of expected range")
        return v
```

**步骤 2：创建 Collector**

```python
# ingestion/collectors/new_collector.py
class NewCollector:
    def __init__(self, minio_client, bucket="sololakehouse", force=False):
        self.minio = minio_client
        self.bucket = bucket
        self.force = force
        self.bronze_writer = BronzeWriter(minio_client, bucket)

    def _fetch_data(self): ...
    def _validate_records(self, raw_data): ...
    def _already_ingested_today(self): ...

    def collect(self) -> dict:
        if not self.force and self._already_ingested_today():
            return {"status": "skipped"}
        raw = self._fetch_data()
        valid, rejected = self._validate_records(raw)
        path = self.bronze_writer.write(pd.DataFrame(valid), source="new_source")
        rejected_path = self.bronze_writer.write_rejected(rejected, source="NEW_SOURCE")
        return {"status": "ok", "valid_count": len(valid), "path": path}
```

**步骤 3：注册 Dagster 资产**

```python
# dagster/assets.py 中新增
@asset(group_name="bronze", retry_policy=RetryPolicy(max_retries=3, delay=5))
def new_source_bronze(context, minio: MinioResource, pipeline_config: PipelineConfigResource):
    result = NewCollector(minio.get_client(), pipeline_config.bucket).collect()
    context.add_output_metadata({"valid_count": result.get("valid_count", 0)})
    return result
```

---

## 附录 D：技术选型的替代方案对比

### D.1 编排层的替代方案

| 工具 | 优点 | 缺点 | 不选原因 |
|------|------|------|---------|
| **Apache Airflow** | 成熟、生态丰富、广泛使用 | 基于任务而非资产，DAG 定义复杂，UI 较陈旧 | 资产语义弱，学习旧式 DAG 建模不符合现代实践 |
| **Prefect** | 现代 API、云服务支持好 | 商业化特征明显，开源版限制较多 | 商业依赖不适合纯开源参考实现 |
| **Mage** | 开发者体验好，内置 IDE | 相对较新，生态较小 | 成熟度和企业参考案例不足 |
| **Dagster** | 资产原生、SDA 模型先进、测试友好 | 学习曲线较陡，两个进程 | **选中**：资产语义与湖仓数据理念高度契合 |

### D.2 存储格式的替代方案

| 格式 | 优点 | 缺点 | 使用场景 |
|------|------|------|---------|
| **Parquet** | 简单、广泛支持、无额外依赖 | 无 ACID、无时间旅行 | Bronze/Silver（当前） |
| **Delta Lake** | ACID 事务、时间旅行、DML 支持 | 需要 Spark 或 Delta standalone | 适合高频 upsert 场景 |
| **Apache Iceberg** | ACID、时间旅行、多引擎支持 | 略复杂的元数据管理 | Gold 层（v2.5 当前） |
| **Apache Hudi** | 近实时 upsert、索引支持 | 生态相对小、配置复杂 | 适合 CDC 管道 |
| **JSON/CSV** | 人类可读 | 极低的查询性能、无列裁剪 | 不适合生产数据湖 |

### D.3 ML 追踪的替代方案

| 工具 | 优点 | 缺点 | 不选原因 |
|------|------|------|---------|
| **MLflow** | 开源、轻量、与主流框架集成好 | UI 功能较基础 | **选中**：开源、自托管、与 XGBoost/LightGBM 无缝集成 |
| **Weights & Biases** | 功能丰富、可视化强大 | 商业服务，需要网络访问 | 不适合完全自托管的参考实现 |
| **DVC** | 版本控制数据+模型、Git 集成好 | 需要 Git 工作流，不自带 UI | 与 MinIO/Trino 生态集成复杂 |
| **Neptune.ai** | 协作功能强 | 商业服务 | 同上 |

### D.4 查询引擎的替代方案

| 工具 | 优点 | 缺点 | 不选原因 |
|------|------|------|---------|
| **Trino** | 多 catalog 联邦、分布式、Hive 兼容 | 内存需求较高、需要 JVM | **选中**：多 catalog 联邦能力无可替代 |
| **DuckDB** | 极快（列式、向量化）、单进程、零依赖 | 单进程、无多 catalog 联邦 | 无法演示 Hive Metastore 集成 |
| **Apache Spark** | 大规模数据处理、生态最全 | 资源重、配置复杂 | 单节点参考不需要分布式计算 |
| **Presto** | Trino 的前身、API 兼容 | 社区分裂后更新较慢 | Trino 是其更活跃的分支 |

---

## 附录 E：项目历史演进摘要

SoloLakehouse 的演进历史记录在 `docs/history/` 目录中，以下是关键里程碑的时间线叙述：

### E.1 v1.0：从零到可运行

项目从一个简单的问题出发：**"一台笔记本能跑起来一个完整的湖仓平台吗？"**

v1.0 的目标被刻意定得简单而清晰：
- 五个核心服务成功连接并健康运行
- 端到端管道：从 ECB API 获取数据，经过 Bronze/Silver/Gold 转换，最终触发 MLflow 实验
- 一条命令启动（`make setup`）

在实现过程中，遇到并解决了几个核心挑战：

**Hive Metastore 的 PostgreSQL 依赖**：Hive Metastore 需要在 PostgreSQL 上创建初始 schema，必须等待 PostgreSQL 完全就绪后才能启动。Docker Compose 的 `depends_on: condition: service_healthy` 解决了这一依赖顺序问题。

**Trino 的 catalog 配置模板化**：Trino 的 catalog 配置文件需要包含 MinIO 凭据，但不能硬编码。`envsubst` + 容器启动脚本的模板展开方案成为最终解法。

**MLflow 的 S3 artifact 存储**：MLflow 将模型文件存储到 S3（MinIO），需要正确配置 `MLFLOW_S3_ENDPOINT_URL` 指向 MinIO，这一配置在早期版本中经常被遗漏。

### E.2 v2.0：从可运行到可运营

v2.0 的触发点是一个真实的痛点：**v1 的管道运行失败时，用户无法知道是哪一步失败了，也没有办法只重试失败的步骤**。

Dagster 的软件定义资产模型直接解决了这两个问题。选择 Dagster 而不是 Airflow 的关键理由是：Dagster 的资产语义比 Airflow 的任务语义更符合数据工程师的思维模型——工程师关心的是 "这份数据是最新的吗？"，而不是 "这个任务有没有运行？"。

v2.0 的一个重要设计约束是：**不能破坏 v1 的工作方式**。这推动了 "Dagster 包装现有逻辑而不重写逻辑" 的架构——v1 的 `ingestion/`、`transformations/`、`ml/` 代码没有任何修改，只是被 Dagster 的 `@asset` 装饰器包裹。

### E.3 v2.5：增量式的现代化

v2.5 是一个 "参考扩展"（reference extension），而不是主要版本。它回答了：**"如果我想在这个平台上体验 Iceberg 和数据目录，需要做什么？"**

答案是：
- Iceberg：修改 `trino_sql.py`，增加两个函数（`refresh_iceberg_gold_from_hive` 已存在的 Hive 表 CTAS 为 Iceberg 表）
- OpenMetadata：新增 `docker-compose.openmetadata.yml`，通过 profile 可选
- Superset：新增 `docker-compose.superset.yml`，预配置 Trino 连接

v2.5 的所有新增都是**加法而不是修改**：没有修改任何 v2.0 已有的代码，新功能通过新文件和可选 profile 引入，完全不影响现有用户。

---

*文档版本：对应 SoloLakehouse v2.5（代码库版本 2026-03-29）*
*撰写基础：源码分析 + 项目文档 + ADR 记录*
