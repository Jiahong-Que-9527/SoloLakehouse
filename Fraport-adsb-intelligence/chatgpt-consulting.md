这个项目有没有必要放在gcp？
我重新考虑了一下你的整个 SLH 项目规划，这个 OpenSky Data Ingestion 项目没有必要一定部署到 GCP，但我建议将最终的数据资产保存在 GCP。

这里要区分两件事情：

Ingestion Compute：在哪里运行下载数据的程序？

Data Storage：下载后的数据保存在哪里？

它们完全可以分开。

而且对于你这个具体项目，我认为本地运行下载程序、GCS 保存数据，可能比一开始就使用 Cloud Run 更合理。

1. 三种架构方案对比
方案 A：全部本地


最简单，成本最低。适合初期开发与数据探索，但后续 GCP 和 Databricks 项目需要额外上传数据。

方案 B：本地计算 + 云端存储

推荐

本地负责下载、验证和恢复，GCS 负责长期存储。后续 BigQuery、Databricks 和 Vertex AI 可以共享同一份数据。

方案 C：全部 GCP


适合长期自动化、定时运行以及无人值守的数据采集，但引入了额外的认证、部署、监控和运行成本。

对比维度

全部本地

本地 + GCS

全部 GCP

开发复杂度

低

低–中

中–高

云端计算成本

无

无

有

本地磁盘压力

高

可控

低

后续云端数据处理

需要迁移

方便

方便

无人值守运行

需自行配置

需自行配置

方便

CI/CD 学习价值

中

中

高

OpenSky 认证复杂度

低

低

需要额外验证

当前项目适合度

高

最高

中

2. 为什么我不建议现在就部署到 Cloud Run？
因为你现在的需求本质上是 Historical Backfill（历史数据回填）。

你想下载一年的历史数据。这可能是一次性的任务，而不是每天必须持续运行的生产服务。

而且：

主要性能瓶颈可能是 OpenSky Trino 的查询速度，而不是你的本地计算能力。

你不需要大量 CPU 或 GPU 来下载数据。

OpenSky 本身存在查询资源限制，使用云计算也不代表可以无限加速。

云端无人值守认证是否可行，还需要实际验证。

你的本地程序完全可以支持断点恢复，并在每个批次完成之后上传到 GCS。

如果仅仅为了下载这一年的数据而引入 Cloud Run、Artifact Registry、Secret Manager、Cloud Scheduler 和完整的 CD pipeline，就有可能变成 Overengineering。

你花费了大量时间解决基础设施问题，却没有真正增加数据资产的价值。

3. 那么这个项目应该做到什么程度？
我会重新定义 Project 01。

Project 01 — OpenSky Historical Data Acquisition
核心目标：

A reliable, reproducible data acquisition tool for building a historical aviation dataset from OpenSky Network.

架构：

OpenSky Trino
Local Python CLI
Batch extraction
Parquet validation
Local staging
Upload to GCS
Commit manifest
Update checkpoint
Next batch
GitHub Actions
Unit tests and lint
Versioned release
你需要实现的功能可以控制在以下范围：

功能

是否必要

OpenSky Trino 连接

必须

CLI 与配置文件

必须

分批下载

必须

Parquet 文件保存

必须

Retry & Checkpoint

必须

Data Manifest

必须

GCS Upload

推荐

pytest

必须

GitHub Actions CI

必须

Docker

可选

Cloud Run

暂时不需要

Cloud Scheduler

暂时不需要

Kubernetes

不需要

这个项目的最终交付物应该是：

一个可靠的数据下载工具 + 一个可追溯的年度航空数据集。

而不是一个复杂的云端部署系统。

4. 那什么时候才应该真正使用 GCP 计算服务？
我认为你的第二个项目才更适合成为 GCP CI/CD 的重点。

Project 02 — Aviation Data Processing Pipeline
假设 Project 01 已经将原始数据保存在 GCS。

接下来你要开发一个程序，从 GCS 读取原始 Parquet，进行清洗、轨迹重建和航班事件识别，再写回 Silver 层。

这个项目就非常适合部署在 GCP 上。

GCS — Bronze

一年 OpenSky 原始 ADS-B 数据
Cloud Run Job / Dataproc Serverless

数据清洗、轨迹重建、事件识别、数据质量检查

GCS — Silver

Clean observations · Arrival events · Trajectories
BigQuery / Databricks / Vertex AI

Analytics · Data Modeling · ML Engineering
为什么这个项目更值得部署到 GCP？

因为：

原始数据已经在 GCS，计算可以靠近数据。

数据转换可能需要更大的计算资源。

你可以不断修改转换逻辑，通过 CI/CD 重新部署并处理数据。

你可以比较单机 Polars、Spark、BigQuery SQL 等不同技术方案。

不再依赖每次访问 OpenSky 的外部认证。

这个阶段，GCP 不再只是为了学习而使用的工具，而是真正解决工程问题的平台。

5. 我会怎样重新规划你的 SLH 项目组合？
项目

主要运行环境

核心职业能力

01 — OpenSky Acquisition

Local + GCS

Python、Ingestion、可靠性

02 — Aviation Transformation

GCP Cloud Run / Dataproc

Cloud Data Engineering、CI/CD

03 — Airport Analytics

BigQuery

SQL、Data Modeling

04 — Aviation Lakehouse

Databricks + GCS

Spark、Delta Lake、Governance

05 — Taxi-in Prediction

Vertex AI

ML Engineering

06 — Model Serving

Cloud Run

MLOps、API、Monitoring

07 — Platform Orchestration

GCP Workflows / Dagster

Platform Architecture

SLH Aviation Portfolio

不是每个项目都必须部署在云端，而是每个项目选择最适合自己的计算环境，并共享数据资产。
6. 从 Platform Owner 的角度，怎样做才是更好的决策？
你现在有一个潜在的盲点：因为你想精通 GCP，所以容易认为每个项目都应该使用 GCP。

但是一个真正的 Cloud Architect 并不是尽可能多地使用云服务，而是能够判断：

Which workloads should run where, and why?

对于一个一次性的、受外部数据源限制的下载任务，本地运行可能是最经济、最简单的选择。

对于反复运行的数据转换任务，云端计算可能更合理。

对于需要持续对外提供预测的服务，Cloud Run 或 Vertex AI Endpoint 才可能有充分的理由。

这种 Workload Placement（工作负载放置决策），本身就是高级架构能力。

你甚至可以在项目中写一份 ADR：

ADR-001: Local Execution for Historical Data Acquisition

Decision:
Run historical data extraction locally and persist
validated datasets in Google Cloud Storage.

Rationale:
- Source-limited workload
- One-time historical backfill
- Lower operational complexity
- No requirement for always-on infrastructure
- Shared cloud storage for downstream workloads

Future:
Migrate ingestion to Cloud Run Jobs if continuous,
unattended ingestion becomes a requirement.
这比为了展示 GCP 而强行部署一个下载脚本更能体现你的架构判断力。

我的最终建议：

现在先在本地完成 Project 01，使用 GitHub 管理代码、GitHub Actions 做 CI、GCS 保存数据（前提是确认 OpenSky 的授权允许个人云端存储）。

等你开始 Project 02，再正式打通 GitHub → Artifact Registry → Cloud Run → GCS 的完整 CI/CD。

这样既不会耽误你学习 GCP，也不会让第一个项目承担过多职责。

对于你未来竞争 €100k+ 的 Data Platform / AI Platform Engineer 岗位，我认为这种有明确取舍、有架构依据、能够持续交付的项目组合，比每个小项目都堆满云服务更有价值。

如果我选择先放到本地，应该用什么方式来存储和管理1年的opensky原始数据呢
如果你决定先把一年的 OpenSky 原始数据保存在本地，我建议你把它设计成一个 Local Raw Data Lake（本地原始数据湖），而不是简单地把下载的文件放进一个文件夹。

但是，这个 Data Lake 不需要部署 MinIO、SeaweedFS、Iceberg、Trino 或者 Kubernetes。

第一阶段最适合你的方案是：本地文件系统 + Apache Parquet + Hive-style Partitioning + Manifest + DuckDB。

这样既足够轻量，又符合现代数据平台的存储设计原则。以后迁移到 GCS、Databricks 或者你的 Proxmox 集群时，基本不需要改变数据的组织方式。

1. 推荐的本地数据存储架构

本地文件系统作为持久化存储，Parquet 作为数据格式，DuckDB 作为查询引擎。三者相互独立。
各组件的职责非常清晰：

组件

职责

SSD / 文件系统

保存完整的原始数据

Parquet

高效保存列式数据

Hive Partitioning

按机场和日期组织文件

JSON Manifest

记录数据来源、完整性和版本

SQLite

管理下载进度与失败恢复

DuckDB

查询、检查和探索数据

GitHub

管理代码、Schema、配置和文档

这里最重要的是：DuckDB 是查询引擎，不是你原始数据的唯一存储位置。 原始数据始终以独立的 Parquet 文件存在。

2. 物理存储：应该把数据放在哪块硬盘？
考虑到你现在正在规划 Proxmox 集群和本地数据平台，我建议暂时不要把这份数据绑定到任何虚拟机或者 Kubernetes 节点。

先把它放在一个独立的数据盘上。

推荐方案
存储设备

用途

主电脑系统盘

Python、IDE、GitHub repository

独立 2TB NVMe SSD

原始数据湖、数据处理、查询

外置 SSD / HDD

数据备份

未来 NAS / Proxmox

共享数据存储

如果你使用 Windows，可以这样组织：

C:\
└── Projects\
    └── SoloLakehouse\

D:\
└── slh-data\
    └── aviation\

E:\
└── slh-backup\
    └── aviation\
如果以后迁移到 Linux：

/opt/sololakehouse/       # 代码
/mnt/slh-data/           # 数据
/mnt/slh-backup/         # 备份
核心原则：代码、数据、备份分离。

不要把一年 ADS-B 数据放进 SLH 的 Git repository 目录，也不要把唯一的数据副本放进某个 Docker container 的文件系统。

一年数据需要多少空间？
现在还无法准确判断，因为你还没有测量所选地理范围、字段数量和压缩后的数据量。

以下是不同数据规模下的容量示例，并非 OpenSky 实测结果：

每天 Parquet 大小

一年 Bronze 数据

100 MB

36.5 GB

250 MB

91.3 GB

500 MB

182.5 GB

1 GB

365 GB

2 GB

730 GB

本地数据湖容量估算
每天压缩后的数据量
500 MB

总数据容量系数

1× 仅原始数据

2× 原始数据 + 备份

3× 原始数据 + 备份 + 衍生数据
一年原始数据
182.5 GB
预计总容量
365.0 GB
建议另外预留约 20%–30% 的空间，用于临时文件、数据处理和未来增长。备份应位于独立设备。
我的建议是先下载七天，测量每天的平均 Parquet 大小，再决定是否需要购买新的 SSD。

如果目前已经有足够的空间，就不用为了这个项目提前购买硬件。

3. 数据目录应该怎么设计？
我建议在本地建立一个独立的 slh-data 根目录，未来不只是航空数据，金融、物流等其他项目也可以采用相同的管理规范。

D:/slh-data/
│
├── aviation/
│   ├── bronze/
│   │   └── opensky/
│   │       ├── state_vectors/
│   │       │   └── v1/
│   │       │       └── airport=EDDF/
│   │       │           └── year=2025/
│   │       │               ├── month=01/
│   │       │               │   ├── day=01/
│   │       │               │   │   ├── hour-00.parquet
│   │       │               │   │   ├── hour-01.parquet
│   │       │               │   │   └── ...
│   │       │               │   ├── day=02/
│   │       │               │   └── ...
│   │       │               └── month=02/
│   │       │
│   │       ├── flights/
│   │       │   └── v1/
│   │       │
│   │       └── aircraft_metadata/
│   │
│   ├── silver/                # 未来项目
│   ├── gold/                  # 未来项目
│   │
│   ├── metadata/
│   │   ├── manifests/
│   │   ├── schemas/
│   │   ├── checkpoint.db
│   │   └── catalog.duckdb
│   │
│   ├── staging/               # 正在下载的临时文件
│   ├── quarantine/            # 未通过验证的文件
│   └── reports/
│       └── dataset-summary.json
│
└── finance/                   # 未来其他业务域
这个结构有几个重要的特点。

3.1 按数据源、数据表、版本和日期分区
例如：

bronze/opensky/state_vectors/v1/
    airport=EDDF/year=2025/month=01/day=01/
这就是 Hive-style Partitioning。

未来 DuckDB、Spark 等工具可以从目录路径自动识别分区字段，并利用分区条件减少不必要的文件读取。

DuckDB

例如，你只想分析 2025 年 3 月的数据，就不需要扫描其他 11 个月的数据。

3.2 为什么要有 v1？
假设你第一版下载数据的范围是：

bounds:
  west: 8.48
  south: 49.98
  east: 8.62
  north: 50.07

后来发现范围太小，无法充分覆盖进近阶段，你想扩大地理范围。

这时候不要直接把新数据覆盖到原来的目录。

应该创建：

state_vectors/
├── v1/    # Airport surface
└── v2/    # Expanded arrival area
因为两个数据集的提取范围不同，实际上已经是两个不同的数据资产。

同样，如果你改变了字段、采样策略或影响数据含义的查询逻辑，也应该评估是否需要新的数据集版本。

4. Parquet 文件具体应该怎么保存？
我建议采用：

属性

推荐设置

文件格式

Apache Parquet

压缩

ZSTD

查询时间窗口

1 小时起步

存储分区

每天

初始文件粒度

每小时

时间标准

UTC

数据类型

明确的 PyArrow Schema

更新策略

已提交原始文件不随意修改

PyArrow 原生支持 Parquet 的 ZSTD、Snappy 等压缩方式，可以直接在写入时配置。

Apache Arrow v24.0.0

例如：

import pyarrow as pa
import pyarrow.parquet as pq

table = pa.Table.from_pandas(
    df,
    preserve_index=False,
)

pq.write_table(
    table,
    "hour-08.parquet",
    compression="zstd",
)

正式版本建议指定明确的 Schema，而不是完全依赖 Pandas 自动推断类型。

保存每小时一个文件，会不会太多？
2025 年全年有 8,760 个小时。

对于一个本地数据湖来说，8,760 个 Parquet 文件并不是特别夸张的规模。

所以第一版我建议直接保存：

day=01/
├── hour-00.parquet
├── hour-01.parquet
├── ...
└── hour-23.parquet
优点是：

每小时可以独立下载。

某个小时失败只需要重新下载该小时。

容易验证是否缺少数据。

不需要等待一天全部下载成功才保存。

程序重启后恢复逻辑简单。

如果以后实际发现文件太小、查询性能受到影响，再进行 Compaction。

Optional Compaction

hour-00

hour-01

hour-02

hour-03

...

hour-23

Merge after validation
part-000.parquet

Daily compacted dataset
不过，Compaction 生成的新文件最好先保存到独立目录，验证行数和完整性，再切换查询入口。不要把合并文件和原始小时文件放在同一个被查询的目录中，否则容易重复计算。

5. 原始数据需要保留哪些字段？
这里需要明确一个概念。

OpenSky 的 state_vectors_data4 是根据接收到的航空无线电消息生成的状态向量，并不是未经处理的底层 ADS-B 二进制消息。

但对于你的 Taxi-in Time 项目，它完全可以作为 Bronze 层的源数据。

我建议保留：

字段

含义

time

状态向量时间

icao24

飞机 ICAO 24-bit 标识

callsign

航班呼号

lat

纬度

lon

经度

velocity

地速

heading

航向

vertrate

垂直速度

onground

地面状态

baroaltitude

气压高度

geoaltitude

几何高度

lastposupdate

最后位置更新时间

lastcontact

最后信号接收时间

hour

OpenSky 小时分区

serials

接收到消息的接收器标识，可选

OpenSky 官方文档确认，状态向量中的速度单位是 m/s，高度是 m，时间是 Unix seconds，hour 是源表的小时级分区列。

The OpenSky Network API 1.4.0 documentation

建议保留源字段的原始含义、类型和单位。

不要在 Bronze 下载时直接做以下操作：

删除缺失 callsign 的记录。

删除速度为零的数据。

仅保留 onground=true。

删除重复观测。

插值缺失轨迹。

推断飞机停车时间。

这些工作都留给后续的数据处理项目。

不过，你的地理范围过滤和字段选择本身已经构成数据提取规则，所以应该将完整 SQL 和提取配置保存在 GitHub，并在 Manifest 中记录。

6. 如何管理这么多数据文件？
这是本地数据湖真正重要的部分。

我建议采用三层管理机制。

第一层：Manifest — 数据资产的身份证
每一个下载批次生成一个 Manifest：

{
  "dataset_id": "opensky_eddf_state_vectors_v1",
  "source": "OpenSky Trino",
  "source_table": "state_vectors_data4",
  "batch_id": "20250101-08",
  "window_start": "2025-01-01T08:00:00Z",
  "window_end": "2025-01-01T09:00:00Z",
  "status": "completed",
  "row_count": 53281,
  "file_size_bytes": 1847296,
  "file_path": "bronze/opensky/state_vectors/v1/airport=EDDF/year=2025/month=01/day=01/hour-08.parquet",
  "compression": "zstd",
  "schema_version": "1.0",
  "checksum_sha256": "<computed-checksum>",
  "git_commit": "<git-commit-sha>"
}

上面的行数和文件大小仅为示例。

Manifest 应该记录：

数据来自哪里；

使用了哪一个版本的提取程序；

下载了哪个时间窗口；

文件有多少行；

文件是否完整；

是否通过验证。

建议将 Manifest 与数据路径保持对应关系。

metadata/manifests/
└── state_vectors/v1/EDDF/2025/01/01/
    ├── hour-00.json
    ├── hour-01.json
    └── ...
Manifest 使用相对路径，不使用 D:\ 这种绝对路径。这样以后迁移到 NAS 或 GCS 时，不需要逐个修改 Manifest。

第二层：SQLite — 管理下载任务
你的 Python 程序可以使用 SQLite 记录下载进度。

例如：

CREATE TABLE ingestion_batches (
    batch_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    row_count INTEGER,
    file_path TEXT,
    file_size_bytes INTEGER,
    error_message TEXT,
    updated_at TEXT
);

通过这个数据库，你可以随时检查：

SELECT
    status,
    COUNT(*) AS batches
FROM ingestion_batches
GROUP BY status;

Annual Ingestion Status

示例数据
● Completed
7,200
● Failed
50
● Empty
10
● Pending
1,500
计划批次：8,760。成功查询但返回零行的批次，应与查询失败的批次分别管理。
需要注意，SQLite 是下载任务的状态管理数据库，而不是存储 ADS-B 观测数据的数据库。

你可以让 SQLite 成为运行时状态索引，而 Manifest 成为已经提交的数据资产记录。如果 SQLite 丢失，可以根据 Manifest 和文件完整性重新建立状态。

第三层：Dataset Summary — 整个数据集的目录
当你下载完一年数据后，应该生成一个年度报告。

{
  "dataset": "opensky_eddf_state_vectors_v1",
  "period": {
    "start": "2025-01-01",
    "end": "2026-01-01"
  },
  "expected_batches": 8760,
  "completed_batches": null,
  "empty_batches": null,
  "failed_batches": null,
  "total_rows": null,
  "total_bytes": null,
  "unique_aircraft": null
}

这些指标由程序自动计算，而不是手动填写。

这份文件以后可以作为 SLH 的 Dataset Catalog 的一部分。

7. 如何查询一整年的数据？—— DuckDB
我非常建议你在 Project 01 中使用 DuckDB。

它会给你一个非常直观的体验：明明没有搭建数据库服务器，却可以像使用数据库一样查询本地的所有 Parquet 文件。

DuckDB: When You Don’t Need Spark (But Still Need SQL) - DEV Community
首先安装：

uv add duckdb

然后创建一个 Python 脚本。

import duckdb

con = duckdb.connect(
    "D:/slh-data/aviation/metadata/catalog.duckdb"
)

con.execute("""
    CREATE OR REPLACE VIEW raw_state_vectors AS
    SELECT *
    FROM read_parquet(
        'D:/slh-data/aviation/bronze/opensky/'
        'state_vectors/v1/**/*.parquet',
        hive_partitioning = true
    )
""")

con.sql("""
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT icao24) AS aircraft_count
    FROM raw_state_vectors
""").show()

DuckDB 支持直接读取 Parquet 文件集合、递归目录和 Hive 分区，也支持查看 Parquet Schema 和文件级元数据。

DuckDB

之后你就可以像查询正常数据库表一样操作。

查询 2025 年 1 月的数据
SELECT *
FROM raw_state_vectors
WHERE airport = 'EDDF'
  AND year = 2025
  AND month = 1
LIMIT 100;

检查每天的观测数量
SELECT
    year,
    month,
    day,
    COUNT(*) AS observations,
    COUNT(DISTINCT icao24) AS aircraft
FROM raw_state_vectors
GROUP BY year, month, day
ORDER BY year, month, day;

检查 ADS-B 地面数据比例
SELECT
    onground,
    COUNT(*) AS observations
FROM raw_state_vectors
GROUP BY onground;

检查某架飞机的完整轨迹
SELECT
    time,
    lat,
    lon,
    velocity,
    heading,
    onground
FROM raw_state_vectors
WHERE icao24 = 'example'
  AND year = 2025
  AND month = 1
  AND day = 1
ORDER BY time;

这样你就建立了一个初步的本地数据查询层。

注意：上面的 DuckDB View 适用于已经提交、验证完成的 Parquet 目录。正式使用时，还可以让查询入口根据 Manifest 生成文件清单，避免读取尚未提交或者被隔离的文件。

8. 需要 MinIO、SeaweedFS 或者 Iceberg 吗？
结合你以前的 SoloLakehouse 架构和现在规划的 Proxmox 集群，我建议你暂时不要引入这些组件。

技术

当前是否需要

什么时候引入

本地文件系统

必须

现在

Parquet

必须

现在

DuckDB

推荐

现在

SQLite

推荐

下载任务管理

SeaweedFS

不需要

多节点共享对象存储时

MinIO

不需要

需要 S3 API 兼容性时

Iceberg

不需要

需要表级快照、演进、事务时

Spark

不需要

单机处理能力不足时

Ceph

不需要

多节点高可用存储时

OpenMetadata

不需要

数据资产和使用者规模增长时

文件数量多，并不自动意味着需要分布式存储。

如果一年数据最终只有几百 GB，一块 SSD 加上 DuckDB 就可能足以支持大量研究和开发工作。

你未来可以把这个项目当成一个非常好的架构演进实验：

Local Parquet + DuckDB
Shared NAS or ObjectStorage
Iceberg + Catalog
Trino / Spark
GCP / Databricksintegration
每次引入新组件，都应该是因为你遇到了真实的需求，而不是因为架构图看起来不够高级。

9. 如何备份和防止数据丢失？
这个数据集一旦下载完，重新获取的成本可能很高，因此备份非常重要。

我建议至少采用：

Primary Data Lake

独立 NVMe SSD · 日常读取和处理
Local Backup

独立外置硬盘或 NAS · 定期备份
Optional Off-site Backup

GCS 或异地存储 · 在数据授权允许的前提下
在 Windows 上，可以使用 Robocopy 做增量复制：

robocopy D:\slh-data\aviation `
         E:\slh-backup\aviation `
         /E /Z /R:3 /W:5

在 Linux 上，可以使用：

rsync -av --progress \
  /mnt/slh-data/aviation/ \
  /mnt/slh-backup/aviation/

这些是复制命令，不等同于完整的版本化备份系统。你还应该定期验证备份能否恢复，并检查文件 checksum。

另外，如果备份正在使用的 SQLite 数据库，建议通过 SQLite Backup API 或者在停止写入后备份，而不是直接复制正在修改的数据库文件。

一个尤其重要的授权问题
我查看了 OpenSky 的官方数据使用条款，其中明确规定：研究结束、研究终止或数据访问及使用权限终止后，原则上需要删除收到的数据副本；科研可复现性需要的合理保留期限存在例外。

opensky-network.org

考虑到你之后还希望将这些数据用于长期 SLH 项目和职业作品集，你最好提前确认个人项目使用权以及研究结束后的保留权限。

保存在本地并不会自动消除数据授权约束。

你可以公开代码、架构和合成数据，但不要默认可以长期持有或公开原始 OpenSky 数据。

10. 我建议你当前实际开发的版本
不要一开始就把上述所有组件做完。

我会把你的 Project 01 分成三个交付版本：

Local Aviation Data Lake Roadmap

0/16
V0.1 — Local Dataset


创建独立 slh-data 数据目录

实现 OpenSky Trino 下载

保存小时级 Parquet 文件

下载一天数据

使用 DuckDB 查询
V0.2 — Managed Dataset


实现按日期分区

定义明确的 PyArrow Schema

实现 SQLite Checkpoint

生成批次 Manifest 和 Checksum

测试重复执行及失败恢复
V1.0 — Annual Data Asset


测量七天数据容量

完成一个月 Backfill 验证

分批完成全年数据下载

生成年度 Dataset Summary

建立备份及恢复流程

发布 GitHub 项目和运行报告
最终，我希望你的系统可以做到：

# 下载一个月
uv run opensky-ingest download \
  --airport EDDF \
  --start 2025-01-01 \
  --end 2025-02-01

# 查看下载进度
uv run opensky-ingest status

# 验证数据完整性
uv run opensky-ingest validate

# 生成数据集报告
uv run opensky-ingest report

这些是建议实现的 CLI 接口，不是现成的命令。

最后的战略建议
对于你现在的 SLH，我甚至建议将这个本地数据湖定义为：

SLH Data Foundation — Aviation Domain

以后形成这样的关系：

GitHub / SoloLakehouse
        │
        │ 代码、配置、数据契约
        ↓
Local Data Foundation
        │
        ├── DuckDB：本地数据分析
        ├── Polars：数据处理
        ├── CatBoost：本地 ML
        ├── GCS：云端数据副本
        ├── Databricks：Lakehouse 实验
        └── Vertex AI：MLOps 实验
这样，你的第一个项目不只是完成一次数据下载，而是在为后续五到十个 Data Engineering、Cloud 和 AI 项目建立共同的数据基础。

对于你未来竞争 €100k+ 的岗位，这种设计有一个很大的优势：你可以展示自己如何在有限资源下做出合理的架构决策，并随着业务需求增长逐步演进平台。

现阶段，先用 Parquet + DuckDB 把数据资产管理好。等你真正需要多节点访问、共享存储、事务和治理时，再引入 SeaweedFS、Iceberg 和分布式计算。 这比一开始就搭建复杂的平台更加符合工程实际，也更体现 Platform Owner 的判断力。





