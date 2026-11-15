# **SoloLakehouse：GCP 与 Databricks 12 个专项项目完整设计**

我建议将这 12 个项目设计成 **两个独立、逐级进阶的工程能力体系**，而不是 12 个普通的数据处理练习。

它们最终应当满足三个目标：

1. **技术成长**：从基础数据工程逐步提升到架构、治理、MLOps 和平台工程。
2. **工程交付**：每个项目都有独立代码、测试、部署、运行和验收证据。
3. **求职竞争力**：能够针对 Data Platform Engineer、Cloud Data Engineer、Lakehouse Engineer、Solutions Architect 和 AI Platform 等岗位，展示不同的能力。

我会保留前面确定的 12 个项目，但进一步明确它们各自的业务问题、数据源、核心功能和最终交付物。

## **一、12 个项目的整体定位**

**GCP Engineering**

# **6 Projects**

Cloud-native Systems

部署、数据服务、分布式消息、治理、ML 与平台自动化。

**Databricks Engineering**

# **6 Projects**

Enterprise Lakehouse

Spark、Delta、工作流、CDC、Unity Catalog、MLflow 与数据平台标准化。

两个系列各自的能力演进

1

G01 · Batch Data

2

G02 · API Serving

3

G03 · Event Processing

4

G04 · Governance

5

G05 · MLOps

6

G06 · Platform Factory

1

D01 · Delta Lake

2

D02 · Lakeflow Jobs

3

D03 · CDC

4

D04 · Unity Catalog

5

D05 · MLflow

6

D06 · Platform Factory

**统一原则：每个项目独立部署，但允许复用前一个项目的数据契约、测试样例和工程经验。**

还有两项经过当前官方文档核对的技术细节：

- GCP 的 Cloud Run Jobs 适合执行有开始和结束的批处理任务，可以通过 Terraform 创建、Cloud Scheduler 定时触发；它与负责 HTTP 服务的 Cloud Run Service 不同。

  [image](https://www.google.com/s2/favicons?domain=https://docs.cloud.google.com\&sz=32)

  Google Cloud Documentation+1

- Databricks Asset Bundles 目前正式称为 **Declarative Automation Bundles**。它适合将 Job、Pipeline、代码和配置统一纳入 CI/CD。2026 年 10 月其 Bundle 部署引擎也发生过变化，因此新项目应采用当前 CLI 和 Bundle 配置，不应照搬旧教程。

  [image](https://www.google.com/s2/favicons?domain=https://docs.databricks.com\&sz=32)

  Databricks on AWS+2



# **二、GCP Engineering：6 个项目的具体设计**

我建议 GCP 系列使用能源、物流、航空和其他适合公开展示的数据，同时围绕不同的工程问题展开，避免所有项目都是简单 ETL。

## **G01 — European Energy Data Pipeline**

Level 1 · Batch Data Engineering

建议第一个实施

[Cloud-Native Advantages of Moving Your ETL Process to Cloud Run | by Averi Kitsch | Google Cloud - Community | Medium](https://images.openai.com/static-rsc-4/pevYRqRnDZwh6n-xuWdggkaMAqy7sx3ba_VCCj4Ano_4I7spGRuAtIIfI369_Mfc1-uAPYMcMhKFLaFnxyVpIsNBivtxmIeM-nAi2YN7DjyD9GTW2UbR-a5U-NAA7J84yc7KRyYkSI-TJHrtUkcypghTMNvv74y8py-cSPTYkjw?purpose=inline)

**业务场景**

建立一个自动更新的欧洲能源市场分析数据集。使用公开的德国和欧洲电力数据，为分析人员提供不同时间段的电力价格、能源结构以及发电量指标。

**推荐数据源：** ENTSO-E Transparency Platform 的公开电力市场数据。注意实际 API 凭据、许可和下载限制；初期使用仓库提供的小型合法样本作为默认输入。

**系统架构**

```
ENTSO-E API / Sample CSV
          |
          v
Cloud Run Job (Python)
          |
          v
Cloud Storage (Raw Files)
          |
          v
Python Validation & Transformation
          |
          v
BigQuery (Clean Tables + Analytics)
          |
          v
SQL Reports / Analysis
```

核心开发任务

1. 编写 Python 数据采集器，支持日期参数和增量下载。
2. 将原始数据按日期分区存入 GCS。
3. 用 Pydantic 或 Pandera 验证 schema、时间戳及关键字段。
4. 生成 BigQuery 数据表及分析 SQL。
5. 使用 Terraform 创建必要资源。
6. 将 Cloud Run Job 连接到 Cloud Scheduler。
7. 使用 GitHub Actions 完成测试、构建和部署。

**关键验收标准**

- 相同输入重复执行，不产生重复业务记录。
- 模拟缺失值、重复行和错误时间戳，验证质量门禁。
- GitHub Actions 在 main 分支发布时完成部署，且具备权限隔离。
- 可以展示 GCP Job ID、BigQuery 结果和测试报告。

**作品展示：** 数据流程架构图、BigQuery SQL 查询结果、GitHub CI 状态、一次端到端运行证据。

**主要体现：** Cloud Data Engineering、IaC、CI/CD、Batch ETL。

## **G02 — European Energy Analytics API**

Level 2 · Cloud-native Application Engineering

[Medium](https://images.openai.com/static-rsc-4/zTJUCRs3cuN-6nnklutkugWX31-VChma1gaCSdb45VRe37qhsylY0UbkSBzGUvg5rRdCm6ltGNjJNxOluULgFyQGMCEUfS4bpOEa33GYkDG7y5RT_Cdy3T7xYfauH3iZuTGOLdnUrIvl7g0NH2n0o1fmMJrWKSCn-A5C_YXdd0o?purpose=inline)

**业务场景**

将 G01 中的能源分析结果包装为受控 API，供网站、分析应用或外部服务消费。

这个项目要回答的问题是：数据已经在 BigQuery 中，如何把它变成一个安全、可靠、可以对外提供的服务？

**系统架构**

```
Client / API Consumer
          |
          v
Authenticated Cloud Run Service
          |
          v
FastAPI + Pydantic
          |
          v
BigQuery Query Layer
          |
          v
JSON Response
```

**建议实现的 API**

| Endpoint                 | 功能           |
| ------------------------ | ------------ |
| `GET /health`            | 健康检查         |
| `GET /v1/prices`         | 按国家和日期查询价格   |
| `GET /v1/generation-mix` | 查询能源结构       |
| `GET /v1/summary`        | 返回统计摘要       |
| `GET /openapi.json`      | OpenAPI 接口定义 |

**核心开发任务**

1. 使用 FastAPI 建立模块化 Web 服务。
2. 使用 Pydantic 定义请求和响应模型。
3. 使用 IAM 身份验证，默认不公开访问。
4. 为 BigQuery 查询设置参数校验、扫描上限及超时策略。
5. 增加结构化日志、异常处理和请求追踪。
6. 使用 pytest 与 HTTP 客户端做自动化测试。
7. 通过 GitHub Actions 部署到 Cloud Run Service。

**进阶设计**

- API 分页与结果缓存；
- 基于 OAuth/OIDC 的受控客户端身份；
- 查询执行时间、错误率和延迟监控；
- 请求参数导致高成本查询时主动拒绝。

**关键验收标准**

- 未授权请求被拒绝。
- 错误参数返回标准化 HTTP 错误。
- 正常查询及无数据场景均有测试。
- 通过小规模负载测试验证延迟与并发表现。

**作品展示：** FastAPI 文档、真实 API 调用、Cloud Run 监控、负载测试报告。

**主要体现：** Software Engineering、Cloud-native Application、API Security。

## **G03 — Aviation Event-driven Processing System**

Level 3 · Distributed Systems & Reliability Engineering

[Event-Driven Architecture on GCP with Pub/Sub & Spring Boot](https://images.openai.com/static-rsc-4/Tf7rNaHfX3gXLg73mWJHD_0FYDMCQE7NnwlWg8is43Ub6cgcM-b-3EEzHtvrfCegZTlT6SnUCOwujFXlcj2pT8C-XcpM7qCnah4vRNZiy8Yj79uR_FZobitvE4Pa2bWPBPhxZyYCj5Pjg_ECSzz-hAaysIw4nfm_N9DSIzVWS2g?purpose=inline)

**业务场景**

模拟机场地面保障事件，例如飞机到达机位、开始卸货、装卸完成及设备离场等。

机场事件可能发生乱序、重复发送或处理失败。这个项目的重点不是处理海量数据，而是构建**可靠的事件驱动系统**。

**推荐数据源：** 自行生成的、符合明确 schema 的合成航空地面事件。

**系统架构**

```
Synthetic Event Generator
          |
          v
       Pub/Sub
          |
          v
Cloud Run Event Consumer
          |
          +----> BigQuery Event History
          |
          +----> Error / Retry Handling
          |
          v
Operational Status Tables

Failed Messages
          |
          v
Dead Letter Topic
```

**事件模型示例**

```
{
  "event_id": "evt-000123",
  "flight_id": "LH123",
  "event_type": "CARGO_UNLOADING_COMPLETE",
  "event_time": "2026-11-15T10:30:00Z",
  "schema_version": "1.0"
}
```

**核心开发任务**

1. 建立事件 schema 与版本验证。
2. 用 Pub/Sub 发布模拟业务事件。
3. 在 Cloud Run Consumer 中解析并处理事件。
4. 设计幂等机制，确保重复投递不会重复产生业务效果。
5. 处理事件发生时间与消息接收时间不同的问题。
6. 实现有限重试、Dead Letter Topic 与人工重放工具。
7. 记录事件处理延迟、失败次数与积压情况。

**必须设计的故障测试**

| 测试场景           | 预期结果                 |
| -------------- | -------------------- |
| 同一个事件发送 3 次    | 仅产生一次业务状态变更          |
| 后发生的事件先到达      | 最终状态仍符合事件版本规则        |
| Schema 缺少必要字段  | 拒绝处理并保留错误证据          |
| BigQuery 暂时不可用 | 可重试，最终不丢失记录          |
| 永久错误事件         | 转入 Dead Letter Topic |

这里需要明确：Pub/Sub 重试和 BigQuery 写入本身不能自动保证业务端到端 exactly-once。你必须通过持久化去重键、事务性设计或确定性的状态更新规则实现幂等，并验证崩溃恢复场景。

**作品展示：** 事件流架构、故障注入测试、Pub/Sub 监控、DLQ 重放演示。

**主要体现：** Distributed Systems、Event-driven Architecture、Operational Reliability。

## **G04 — Governed Energy Data Product**

Level 4 · Data Governance & Data Product Engineering

[Building a data mesh on Google Cloud using BigQuery and Dataplex | Google Cloud Blog](https://images.openai.com/static-rsc-4/zvNsYLbqe--qjgKvQdxZef0mYGuKm8WPNJoLSPw8WRXoL8qap6bcR_eBDediV7q06XHzaLOOe1m4VYfoo4pigs752CufPj_uwVOcGZK1PbBpXpG9FEh4mfd1Cu_-7UBjAIw2QG1bTrXzH4UnKLgZAMZq66-Q9pvuUD06dWrI3tk?purpose=inline)

**业务场景**

模拟一家欧洲能源企业的数据平台。数据生产团队负责发布能源数据，而不同的业务团队只能使用经过质量检查且符合访问权限的数据产品。

核心问题是：**如何确保只有合格的数据才能进入生产环境，并且可以追踪数据来源、发布人、版本和消费者？**

这是 GCP 系列中最值得深入建设的项目之一。

**系统架构**

```
Source Dataset
      |
      v
Schema Contract Validation
      |
      v
Data Quality Gate
      |
      +---- Fail ---> Quarantine + Report
      |
      v
Approved Release
      |
      v
BigQuery Published Tables
      |
      +----> IAM / Authorized Views
      +----> Data Catalog / Lineage
      +----> Audit Logs
      |
      v
Consumer Data Product
```

Google Cloud 的 Dataplex Universal Catalog 已更名为 Knowledge Catalog；相关数据血缘功能可以与 BigQuery 等服务集成，实际可见范围取决于权限、API 和资源配置。

[image](https://www.google.com/s2/favicons?domain=https://docs.cloud.google.com\&sz=32)

Google Cloud Documentation



**推荐设计三个数据产品：**

| 数据产品                   | 内容       | 消费者                 |
| ---------------------- | -------- | ------------------- |
| Energy Price Analytics | 每小时电价    | Market Analyst      |
| Renewable Generation   | 可再生能源发电量 | Sustainability Team |
| Energy Summary         | 每日聚合指标   | Management          |

**核心开发任务**

1. 为各数据产品定义 YAML 或 JSON 数据契约。
2. 实现 schema compatibility checks。
3. 设置 freshness、completeness、uniqueness 和范围检查。
4. 建立校验失败后的隔离与阻断机制。
5. 为 Data Producer、Analyst、Auditor 设计访问权限。
6. 建立源数据到发布表的 lineage。
7. 将数据集版本、校验结果和 Git commit 关联起来。
8. 实现发布、撤回及重新发布流程。

**建议形成的发布清单**

```
data_product: energy-prices
version: 1.2.0

contract:
  schema_version: 2
  required_columns:
    - timestamp
    - country
    - price_eur_mwh

quality_gates:
  completeness_min: 0.99
  duplicate_business_keys_max: 0
  freshness_hours_max: 48

release:
  approval_required: true
  record_manifest: true
```

这些阈值是初始设计值，应根据数据源实际更新频率、历史延迟和业务要求调整。

**关键验收标准**

- 注入错误数据后，发布流程自动阻断。
- 授权用户只能读取被允许的数据产品。
- 每次发布可以关联代码版本、源数据版本和质量报告。
- 可以演示一次数据产品回滚或重新发布。

**作品展示：** Data Contract、Quality Gate、IAM 权限测试、血缘图、Release Manifest。

**主要体现：** Data Governance、Compliance-by-design、Data Product Ownership。

这会是你申请银行、保险、工业和大型国际企业 Data Platform 岗位时，非常值得展示的工程能力。

## **G05 — Energy Forecasting MLOps**

Level 5 · Machine Learning Platform Engineering

[TensorFlow Extended、Vertex AI Pipelines、Cloud Build を使用した MLOps のアーキテクチャ  |  Cloud Architecture Center  |  Google Cloud Documentation](https://images.openai.com/static-rsc-4/VoyKm78t5lPtkdxipos3SVmZ8rBMzEicxSdJbOiYH3pmkHOt7Fu31GMxaU0AfmXfC62LJS2z2JakjBnQAl9HZIAWmdyGT789QKF1zHcKlRfF22VPG7aQzEOV1Ysg6Zg5gcCSLJVD4PGTOPUV9PWqbanCTFDgmTsU6pDmi05LBlM?purpose=inline)

**业务场景**

根据历史电价、发电量、日历信息及可获得的天气数据，建立短期电价预测模型。

这个项目的重点不是开发最复杂的预测算法，而是证明你能管理**机器学习模型的完整工程生命周期**。

**系统架构**

```
BigQuery / Sample Dataset
          |
          v
Feature Preparation
          |
          v
Vertex AI Training Pipeline
          |
          v
ML Evaluation & Quality Gate
          |
          v
Vertex AI Model Registry
          |
          v
Batch Prediction / Cloud Run
          |
          v
Prediction Monitoring
```

**核心开发任务**

1. 实现可重复的训练数据构建。
2. 使用时间序列切分，而不是随机拆分训练集和测试集。
3. 建立 Baseline，例如季节性 Naive Forecast。
4. 训练 CatBoost、LightGBM 或类似模型。
5. 记录训练参数、数据版本和性能。
6. 使用 Vertex AI Pipelines 串联训练、评估与注册。
7. 通过模型质量门禁决定是否晋升模型版本。
8. 实现批量预测、监控和回退机制。

**建议评估指标**

| 类别                 | 指标                                   |
| ------------------ | ------------------------------------ |
| Accuracy           | MAE、RMSE                             |
| Robustness         | 不同季节与价格波动区间的误差                       |
| Data Quality       | Missing Rate、Freshness               |
| Prediction Quality | Prediction Drift、Residual Drift      |
| Operations         | Pipeline Success Rate、Execution Cost |

**关键验收标准**

- 同一个数据版本和配置可以复现训练结果，允许有记录的数值浮动。
- 性能不合格的模型不能自动晋升。
- 可以查询旧模型的参数、代码版本和评估结果。
- 推理失败时支持回滚到上一个可用模型。

**成本控制建议：** 优先使用小数据集、CPU 训练和批量推理。不要为了展示 MLOps 而持续运行昂贵的在线预测端点。

**作品展示：** Vertex AI Pipeline、Model Registry、模型质量对比、部署及回滚演示。

**主要体现：** MLOps、ML Platform、Model Lifecycle Ownership。

## **G06 — Reproducible GCP Platform Factory**

Level 6 · Cloud Platform Engineering

高级重点项目

[GitHub Actions を使って Google Cloud 環境に Terraform を実行する方法 - G-gen Tech Blog](https://images.openai.com/static-rsc-4/wG4art1vaL9RrUojbruGkpxTNoVm5aLhIUeTQb3BhxviXJZoA6dEUx8D3Vi7Kb3U_0KxEXJuaNEf9KwUbjivwovULucgai9f0G_gb1fO_3rZW6Wsdzzr9mM9TiFCSiYNvrQmxkatipjWepy0x60me8_AStTU8OZao1MjVmoQtAk?purpose=inline)

**业务场景**

假设你是一个企业 Data Platform Team 的工程师。公司不断出现新数据项目，每个团队都需要 GCP 环境、身份权限、CI/CD、日志和成本控制。

如果每个项目都从零开始搭建，既浪费时间，也会导致安全和治理标准不一致。

G06 的目标是建立一套 **Self-service Cloud Project Template**。

**系统架构**

```
Developer / New Project
          |
          v
Project Template
          |
          v
GitHub Repository
          |
          v
GitHub Actions
          |
          v
OIDC / Workload Identity Federation
          |
          v
Terraform Provisioning
          |
          +----> Cloud Storage
          +----> BigQuery
          +----> Cloud Run
          +----> IAM
          +----> Logging / Budget
          |
          v
Deploy + Verify + Evidence
```

Google Cloud 支持 GitHub Actions 通过 OIDC 和 Workload Identity Federation 获取短期凭据，避免将长期 Service Account Key 存在 GitHub Secrets 中。

[image](https://www.google.com/s2/favicons?domain=https://docs.cloud.google.com\&sz=32)

Google Cloud Documentation



**核心开发任务**

1. 建立标准 Terraform Module。
2. 创建可复用的 GitHub Actions Workflow。
3. 使用 OIDC/WIF 配置安全部署身份。
4. 统一 dev、test、prod 的部署参数与权限范围。
5. 实现项目级 IAM 最小权限。
6. 增加 Terraform format、validate、plan 和安全检查。
7. 建立日志、成本归属和预算告警。
8. 支持项目自动创建、验证及可控销毁。
9. 记录每次部署的资源清单和验证结果。

**建议提供三种模板**

| 模板                    | 自动创建资源                        | 适用场景 |
| --------------------- | ----------------------------- | ---- |
| Batch Data Pipeline   | GCS、Cloud Run Job、BigQuery    | 数据工程 |
| Serverless API        | Cloud Run Service、IAM、Logging | 应用服务 |
| Governed Data Product | BigQuery、IAM、质量与发布流程          | 数据治理 |

**关键验收标准**

- 新开发者使用模板可以创建一个新项目。
- 不需要人工复制长期云服务密钥。
- 不同项目的资源和权限相互隔离。
- Terraform 重复应用不产生不必要的变更。
- 可以通过受控流程销毁项目资源，避免持续收费。

**作品展示：** Project Factory Demo、Terraform Modules、GitHub Actions、部署日志、成本报告。

**主要体现：** Platform Engineering、Developer Experience、Infrastructure Ownership。

这个项目的层级明显高于一个普通的 Cloud Engineer Demo。

你不再只是使用别人提供的平台，而是在设计让其他开发者使用的平台。但要真正证明这点，最好让一个独立项目或其他使用者实际采用你的模板，并记录使用过程中的问题与改进。

# **三、Databricks Engineering：6 个项目的具体设计**

Databricks 系列建议以 **ECB 公开金融数据 + 可控的模拟交易数据** 为主线。

这样能够利用你对 ECB 数据已经积累的经验，同时逐步建立 Spark、Delta Lake、增量处理、治理与 ML 工程能力。

我不建议所有项目都简单地把同一份 CSV 读入 Delta 表。每个项目应该解决一个明显不同的工程问题。

## **D01 — ECB Delta Lakehouse**

Level 1 · Spark & Delta Fundamentals

建议第一个实施

[Databricks The Medallion Architecture - EndToEndData - Medium](https://images.openai.com/static-rsc-4/m5FM23jX83kZnBDPCZKxELBElvsxikkL2ghxOHRrJ0nMCy781545fn82SyGbO-_ULBc2f88LpArg3lzvnRt5MvKOYdzFTce4yaroqOd0A8smV1u3MeNWHxWNUlCJ02cM_473k89nG2d3bdedgsPMG7dzM_wAojWnigFxNBcHMjM?purpose=inline)

**业务场景**

建立欧洲央行金融指标数据湖，整合 ECB 的利率、汇率与其他公开时间序列，提供统一的金融分析表。

**推荐数据源：** ECB Data Portal / SDMX API。

**系统架构**

```
ECB SDMX / Versioned Samples
          |
          v
Bronze Delta Tables
          |
          v
Silver Delta Tables
  - Type Cleaning
  - Deduplication
  - Missing Value Handling
          |
          v
Gold Delta Tables
          |
          v
Databricks SQL / Dashboard
```

**建议建立的数据表**

| 数据层    | 示例表                                                 |
| ------ | --------------------------------------------------- |
| Bronze | `raw_ecb_rates`、`raw_fx_rates`                      |
| Silver | `clean_interest_rates`、`clean_fx_rates`             |
| Gold   | `daily_euro_indicators`、`monthly_financial_summary` |

**核心开发任务**

1. 使用 PySpark 读取 CSV、JSON 或 Parquet。
2. 建立 Bronze、Silver、Gold 表。
3. 进行 Schema Validation。
4. 使用 Delta MERGE 做增量更新。
5. 实践表版本和 Time Travel。
6. 使用 SQL 生成利率趋势和汇率分析结果。
7. 将数据处理逻辑封装为 Python 函数，并用 pytest 测试。

**关键验收标准**

- 同一个数据集重复运行，不产生重复业务记录。
- 增加新日期的数据后，只处理需要更新的数据。
- 可以演示 Delta 表的历史版本查询。
- 可以根据预先定义的规则处理 schema 变更。

**作品展示：** Medallion Architecture、Delta Table History、PySpark Tests、SQL Dashboard。

**主要体现：** Apache Spark、Delta Lake、数据建模和 ETL 基础。

## **D02 — Financial ETL Automation**

Level 2 · Orchestration & Databricks CI/CD

[Jobs do Lakeflow | Databricks on Google Cloud](https://images.openai.com/static-rsc-4/-KmWiJ3k_2vfBC2CcmBcZNFs61uBkVOwWZcJtwKZwI-hMTqoHksGrPkU1kxzyW1HaZgXWMCAacMDLw9FNhyYwxUF6pmavCskttYW14mH2ka5iXbyN6OQAVX3eV9XkFZZDf4KB6OyLUSDQk-6O1QzQhPEUxuL_wUE5E4JOP4qvjg?purpose=inline)

**业务场景**

D01 已经可以把金融数据转换为 Delta 表，但企业数据平台不能依靠工程师手动运行 Notebook。

D02 重点解决自动调度、任务依赖、部署和失败恢复。

**系统架构**

```
GitHub Repository
       |
       v
CI: Tests + Bundle Validation
       |
       v
Declarative Automation Bundles
       |
       v
Databricks Workspace
       |
       v
Lakeflow Jobs
       |
       +--> Ingest
       |       |
       |       v
       +--> Transform
       |       |
       |       v
       +--> Quality Check
       |       |
       |       v
       +--> Publish
       |
       v
Run Evidence / Alerts
```

**核心开发任务**

1. 将 D01 的 Python 代码拆分为可独立执行的任务。
2. 建立 Lakeflow Jobs 的任务依赖。
3. 为任务配置失败重试、超时及参数。
4. 使用 Declarative Automation Bundles 定义部署资源。
5. 支持开发与生产环境的不同配置。
6. 通过 GitHub Actions 执行测试与 Bundle Validation。
7. 自动部署 Job。
8. 记录每次运行的状态、持续时间及输入数据版本。

**进阶场景**

- 上游采集失败时，阻止下游发布。
- 质量检查失败时，保留旧版本 Gold 表。
- 支持指定历史日期重新处理。
- 对重试和手动重新运行保持幂等。

**关键验收标准**

- 可从 GitHub 部署 Lakeflow Job。
- 运行失败后可定位具体失败任务。
- 支持指定日期 Backfill。
- 能够展示部署版本与运行版本之间的关系。

**作品展示：** Job DAG、Bundle YAML、GitHub Actions、任务失败与恢复日志。

**主要体现：** DataOps、Workflow Orchestration、CI/CD、Production Operations。

## **D03 — Financial Transaction CDC Lakehouse**

Level 3 · Streaming & Incremental Data Engineering

[Simplifying CDC and Incremental Loads with Auto Loader & Delta Tables](https://images.openai.com/static-rsc-4/TlmN5ynUbEiCRHHsB893ybiOR_tjXVVZneSRxOvBJY7krCeE9tW8v3AvEar_kbpZcJwt9V613Yj5vmcK1QZouRUREG_qTdziCdnsLp1DoMzm3DU-htzkMK-BYIh4vzcl_Lmnq_GDhQNcmWEpWPyweKiw2AbRmM3_GZFX4u_edts?purpose=inline)

**业务场景**

模拟支付或银行交易系统，持续产生交易状态变化。

例如一笔交易最初为 `PENDING`，随后变为 `COMPLETED`，也可能被取消。源系统会重复发送记录、延迟发送旧版本，甚至发生修正。

**推荐数据源：** 使用 Python 或 Faker 生成包含 insert、update、delete 操作的合成 CDC 数据。

**系统架构**

```
Synthetic Transaction Source
            |
            v
Append-only CDC Files
            |
            v
Databricks Auto Loader
            |
            v
Bronze CDC Event Table
            |
            v
Incremental Processing
            |
            +--> Current State Table
            |
            +--> Transaction History
            |
            v
Gold Financial Metrics
```

**建议 CDC 数据结构**

```
{
  "transaction_id": "tx-10001",
  "operation": "UPDATE",
  "sequence_number": 3,
  "status": "COMPLETED",
  "amount": 250.0,
  "currency": "EUR",
  "event_time": "2026-11-15T10:30:00Z"
}
```

**核心开发任务**

1. 建立 CDC 数据生成器，提供可复现测试样本。
2. 使用 Auto Loader 增量发现新文件。
3. 建立 Bronze 追加事件表。
4. 根据事件序列号、业务键和操作类型维护当前状态。
5. 实现删除、更新和历史记录。
6. 配置 checkpoint 和失败恢复。
7. 使用 AUTO CDC 或 Structured Streaming + MERGE 实现 CDC，比较两种方法的特点。
8. 实现 Backfill、事件重放和数据一致性检查。

**必须完成的测试**

| 场景            | 验收目标         |
| ------------- | ------------ |
| 重复事件          | 当前状态不重复更新    |
| 乱序事件          | 旧版本不覆盖新版本    |
| 交易取消          | 最终状态正确       |
| Processing 中断 | 恢复后结果一致      |
| 历史数据回放        | 与确定性全量重算结果一致 |

注意不要把 Auto Loader 误认为完整 CDC 引擎。Auto Loader 主要处理文件的增量发现与摄取；业务 CDC 更新逻辑仍需要明确设计。

**作品展示：** CDC 事件流、Delta MERGE、Checkpoint Recovery、数据一致性测试。

**主要体现：** Incremental Processing、Streaming、Data Consistency、Fault Recovery。

这是我认为 Databricks 系列中**非常值得深入做**的项目，因为它能直接对应很多企业数据平台的生产问题。

## **D04 — Unity Catalog Governance**

Level 4 · Enterprise Data Governance

[Modern data platforms don’t fail because of scale — they fail because of poor governance. Unity Catalog changes that equation | by Aman Maheshwari | Feb, 2026 | Medium](https://images.openai.com/static-rsc-4/dH5et-W5hNTGq-RclDRlinkrlzCHsREjFnvnrPCfuimi330RBYm1myFc_jRlfhZB8M_ALfxvWPB850vCjq-SFp55z-gOlzM-J3jQBUA2Vjk84nlj0Qk2SA7e2Q1peyJhUQjXbcax0V5YpL7jqrYU8xPTqqrzVswSR0erixqpVgY?purpose=inline)

**业务场景**

模拟企业内部多个团队共享金融数据的平台。

数据工程团队负责生产表，分析师只需查询公开业务指标，而风险管理团队可以查看更细的数据。不同团队不应该拥有相同的权限。

**系统架构**

```
Databricks Workspace
          |
          v
Unity Catalog
          |
          +--> Finance Catalog
          |       |
          |       +--> Bronze
          |       +--> Silver
          |       +--> Gold
          |
          +--> Consumer Views
          |
          +--> Permissions
          |
          +--> Lineage / Audit
```

**建议设计角色**

| 角色            | 数据访问能力             |
| ------------- | ------------------ |
| Data Engineer | 在指定 schema 创建和维护数据 |
| Data Analyst  | 只读 Gold 指标         |
| Risk Analyst  | 读取经授权的风险明细         |
| ML Engineer   | 读取获批准的特征数据         |
| Auditor       | 查看必要的元数据和审计证据      |

**核心开发任务**

1. 设计 Catalog / Schema 命名和所有权。
2. 使用 Unity Catalog 创建受治理的 Delta Tables。
3. 实现 GRANT、REVOKE 和最小权限策略。
4. 为敏感交易字段设计列级保护或受控视图。
5. 建立开发与生产环境隔离。
6. 使用 Data Lineage 查看表之间的依赖。
7. 增加数据质量检查与发布控制。
8. 记录权限变更及访问审计证据。

**进阶设计**

对于包含姓名、账号或其他敏感字段的模拟交易数据，可以比较两种治理方式：Authorized/Controlled Views 与 Column Masking。

**关键验收标准**

- Data Analyst 无法访问 Bronze 明细。
- Risk Analyst 能读取指定的受控数据。
- 权限被撤销后访问失败。
- 可以查看从 Bronze 到 Gold 的数据血缘。
- 可以给出一次权限变更的审计记录。

**作品展示：** Unity Catalog 结构、权限矩阵、血缘图、访问控制测试。

**主要体现：** Unity Catalog、Data Security、Data Governance、Enterprise Architecture。

需要说明的是，某些账号管理、审计或企业安全功能可能不在 Databricks Free Edition 中提供。因此应将基础 Catalog 治理和企业级扩展分开验收，不要把权限不允许执行的功能写成已交付。

## **D05 — Financial Forecasting MLOps**

Level 5 · ML Engineering & Model Lifecycle

[MLflow on Databricks | Databricks on Google Cloud](https://images.openai.com/static-rsc-4/iXImc_W7SuQeXi7cZAXBVKHQpJrjJchfp-YTUhz2HIqq-EZ39AfdgfBcwaFeSM7vBCph6q-MuyLMmPH8GGD_gWXC7I5-RMwd3OScPAjxapUKuFfsYmw2m74tGadpLegSsUgbnv5lZ10V9Jju2JesyNTCIAmtPC7_Y_rq74aWsJ8?purpose=inline)

**业务场景**

利用 ECB 金融时间序列预测短期金融指标的变化，并建立可复现的模型训练和发布机制。

建议先选择**下一期利率或汇率变化预测的研究性实验**，而非构建真实交易决策系统。金融市场预测存在明显的非平稳性，模型结果不应被包装为可盈利的交易策略。

**系统架构**

```
Gold Delta Tables
        |
        v
Feature Engineering
        |
        v
ML Training
        |
        v
MLflow Experiment Tracking
        |
        v
Model Evaluation Gate
        |
        v
Unity Catalog Model Registry
        |
        v
Batch Prediction Job
        |
        v
Prediction Monitoring
```

**核心开发任务**

1. 从 Delta Gold 表构建训练数据集。
2. 定义特征生成时点，避免未来数据泄漏。
3. 建立 Naive Forecast、Linear Regression 等 Baseline。
4. 尝试 Gradient Boosting 或其他适合表格数据的模型。
5. 使用 MLflow 记录实验参数、指标及 Artifact。
6. 建立 Model Registry 和模型版本管理。
7. 使用 Lakeflow Job 自动执行批量预测。
8. 记录预测误差和数据漂移。
9. 实现模型回退流程。

**重点训练三个能力**

- **Reproducibility**：数据、代码、参数可追溯。
- **Model Governance**：什么条件下允许发布新模型。
- **Operational MLOps**：模型发布后如何发现质量下降。

**关键验收标准**

- 有清晰的基线模型和滚动时间验证。
- 不合格模型被质量门禁阻止发布。
- 每个模型版本可以追溯训练数据和 Git commit。
- 可以使用指定旧版本重新生成预测结果。
- 监控结果能够提示模型退化。

**作品展示：** MLflow Experiment、Model Registry、Evaluation Report、Prediction Monitoring。

**主要体现：** MLflow、Feature Engineering、MLOps、Model Governance。

## **D06 — Enterprise Lakehouse Platform Factory**

Level 6 · Lakehouse Platform Engineering

高级重点项目

[The keys to production Data & AI applications with Azure Databricks | by Arun Wagle | Databricks Platform SME | Medium](https://images.openai.com/static-rsc-4/maYuS50SysitRYcutbWe3wr3Kj3DniB5DPmgvbTG67q3dK5DGzgG64JsByRIoAy6GRtO5g6UWYkleKBQf3aqujyxcT7BzQe46E6xj31ytVtJR6G8eZC4vjIp7OQbEL0tRsZa3O_ORV1oLzmuqMAiRZzuBFPSRNHo9Y4oTbdh4JM?purpose=inline)

**业务场景**

假设你负责企业的 Databricks 平台，每个部门都需要自己的数据项目。

金融部门想创建一个交易分析 Pipeline，物流部门想创建一个运营指标 Pipeline，AI 团队想创建特征表和训练任务。

如果每个部门都需要平台团队手动配置 Catalog、权限、Job 和 CI/CD，交付效率就会很低。

D06 旨在把这些步骤标准化，让新团队能够通过模板创建数据项目。

**系统架构**

```
New Data Team
       |
       v
Lakehouse Project Template
       |
       v
GitHub Repository
       |
       v
GitHub Actions
       |
       v
Databricks CLI / Bundle
       |
       v
Workspace Resources
       |
       +--> Catalog / Schema
       +--> Lakeflow Jobs
       +--> Delta Tables
       +--> Access Controls
       +--> Quality Gates
       |
       v
Deployment & Validation Report
```

**建议提供三种模板**

| 模板                    | 主要功能                                     |
| --------------------- | ---------------------------------------- |
| Batch Lakehouse       | Bronze / Silver / Gold、Jobs、Data Quality |
| Incremental Lakehouse | Auto Loader、CDC、Checkpoint、MERGE         |
| ML Engineering        | Feature Pipeline、MLflow、Model Registry   |

**核心开发任务**

1. 开发标准 Databricks Bundle Template。
2. 将 Catalog、Schema 和基础权限通过 IaC 管理。
3. 使用 Bundle 定义数据处理任务、参数和部署目标。
4. 建立 dev / prod 配置隔离。
5. 统一项目单元测试、集成测试和数据质量测试。
6. 自动生成项目 README 与部署说明。
7. 支持创建和销毁测试资源。
8. 建立运行和部署审计证据。
9. 编写平台使用指南和故障排查 Runbook。

**推荐的工程边界**

Terraform 负责工作区、账户、权限等适合通过 Provider 管理的基础设施资源；Declarative Automation Bundles 负责数据项目中的 Jobs、Pipelines、Notebook 和其他受支持资源。

不应让 Terraform 和 Bundle 同时管理同一个资源，避免产生配置漂移和所有权冲突。

**关键验收标准**

- 可以通过模板创建新的 Batch Lakehouse。
- 新项目可以独立部署和测试。
- 模板生成的项目符合统一权限和质量规范。
- 新项目从创建到首次运行不需要手动复制配置。
- 能展示创建、验证、更新和销毁的完整过程。

**作品展示：** Lakehouse Template、Bundle、权限定义、自动部署、开发者操作指南。

**主要体现：** Lakehouse Platform Engineering、DataOps、Developer Experience、Platform Ownership。

这个项目与 G06 一样，是你从单一项目开发者转向平台建设者的重要作品。

# **四、12 个项目如何组织成真正的平台工程作品集？**

## **1. 目录结构**

我建议全部项目采用统一模板，但允许 GCP 和 Databricks 使用各自适合的部署工具。

```
SoloLakehouse/
│
├── Fraport-adsb-intelligence/
│
├── gcp/
│   ├── 01-european-energy-pipeline/
│   ├── 02-energy-analytics-api/
│   ├── 03-aviation-event-processing/
│   ├── 04-governed-energy-data-product/
│   ├── 05-energy-forecasting-mlops/
│   └── 06-cloud-platform-factory/
│
├── databricks/
│   ├── 01-ecb-delta-lakehouse/
│   ├── 02-financial-etl-automation/
│   ├── 03-financial-cdc-lakehouse/
│   ├── 04-unity-catalog-governance/
│   ├── 05-financial-forecasting-mlops/
│   └── 06-lakehouse-platform-factory/
│
├── local/
├── project-template/
├── docs/
└── .github/workflows/
```

每个专项项目都应该包含以下基本内容：

```
project/
├── README.md
├── src/
├── tests/
├── config/
├── infrastructure/
├── data/
│   └── samples/
├── docs/
│   ├── architecture.md
│   ├── decisions/
│   └── runbook.md
├── evidence/
│   └── README.md
├── pyproject.toml
└── Makefile
```

Databricks 项目另外放置 `databricks.yml` 和 Bundle 资源定义，GCP 项目则根据需要放置 Terraform、Dockerfile 和 Cloud Run 配置。

**Evidence 是所有项目都应该保留的关键目录。** 不需要提交海量运行日志，但应该记录真实运行的链接、版本、摘要、截图或经过脱敏的验收报告。

## **2. 不同项目的依赖关系**

为了保持独立部署，建议把共享内容分为三种：

| 内容               | 处理方式            |
| ---------------- | --------------- |
| 数据格式、Schema、质量规范 | 允许复用，并且版本化      |
| 通用部署规范、测试模板      | 在项目创建时生成或引用     |
| 已部署的云资源、数据库、工作区  | 不作为另一个项目的默认运行依赖 |

例如，G02 在实际展示时可以查询 G01 生成的 BigQuery 数据，但它也应提供独立样本表的初始化方式。这样招聘方无需先部署 G01 就能测试 G02。

# **五、实施优先级与投入建议**

考虑到你目前还在推进航空旗舰项目以及求职，我不建议一次性启动 12 个项目。

下面的评分强调**对你当前求职方向的边际价值**，而不是对技术本身的重要性排序。

**项目优先级总表**

全部GCPDatabricks

| 项目                        | 优先级 | 工时估算    |
| ------------------------- | --- | ------- |
| G01 Energy Pipeline       | P0  | 20–35 h |
| G02 Analytics API         | P1  | 15–25 h |
| G03 Event Processing      | P1  | 30–50 h |
| G04 Governed Data Product | P0  | 30–50 h |
| G05 Vertex AI MLOps       | P2  | 35–60 h |
| G06 Platform Factory      | P2  | 50–90 h |
| D01 ECB Delta Lakehouse   | P0  | 15–25 h |
| D02 Financial ETL         | P0  | 20–35 h |
| D03 Financial CDC         | P1  | 35–60 h |
| D04 Unity Governance      | P1  | 25–45 h |
| D05 Financial MLOps       | P2  | 30–50 h |
| D06 Platform Factory      | P2  | 45–80 h |

工时为粗略的个人开发估算，假设你已熟悉 Python、Git、Docker 和基本云服务，不包括长期运维及大量调试。实际投入可能明显增加。

## **六、云端成本应该如何控制？**

你之前提出过 GCP 每月约 $100 的实验预算。我建议将这作为**预算上限**，而不是必须花完的目标。

| 项目类型               | 成本控制策略                              |
| ------------------ | ----------------------------------- |
| G01 / G02          | 小数据集、按需运行、Cloud Run 闲时缩零            |
| G03                | 少量消息、短时故障实验、避免持续生成事件                |
| G04                | 小型 BigQuery 数据集、最小查询量、按需启用治理功能      |
| G05                | CPU 小样本训练、按需批量推理、避免长期在线端点           |
| G06                | 临时环境、预算告警、实验后销毁资源                   |
| Databricks D01–D06 | 优先使用 Free Edition；不支持的企业功能再按需使用付费环境 |

Databricks Free Edition 对 Compute、并发任务、Lakeflow Pipelines 和企业管理能力存在限制，例如 Jobs 并发任务数上限及部分账户级管理功能不可用。它适合初期学习，但不能假设全部 6 个项目都能完整免费落地。

[image](https://www.google.com/s2/favicons?domain=https://docs.databricks.com\&sz=32)

Databricks on AWS



同时，GCP 的预算告警并非硬性支出熔断器。真正控制风险，需要结合服务配额、最大实例数、查询限制、自动清理和人为审批。

# **七、我的最终建议：先完成 4 个最能改变求职叙事的项目**

第一批重点交付

GCP 基础

**G01**

Energy Pipeline

证明 Cloud Deployment + CI/CD

Databricks 基础

**D01**

ECB Delta Lakehouse

证明 Spark + Delta Engineering

生产化能力

**D02**

Financial ETL Automation

证明 DataOps + Job Lifecycle

治理能力

**G04**

Governed Data Product

证明 Quality Gate + Data Ownership

选择这四个，是因为它们与 Fraport ADS-B Intelligence 构成互补：

- **G01**：你能够在公有云交付数据系统。
- **D01 / D02**：你能够使用 Databricks 构建并运行 Lakehouse Workflow。
- **G04**：你能够为数据定义质量和治理边界。
- **Fraport ADS-B Intelligence**：你能够把这些能力用于一个真实且具有行业背景的综合工程问题。

这比在 CV 中单纯写出 GCP、Databricks、Spark、Kubernetes、Terraform 等技术名词更有价值。

而等到上述项目完成，再选择 **D03 CDC、D04 Unity Catalog 或 G06 Platform Factory** 深入建设，才是更有效率的升级路径。

**你最终应该向招聘方证明的，不是“我学习过 12 项技术”，而是“我建立了一套可重复交付数据与 AI 系统的工程方法，并用多个真实项目验证了它”。**

这套思路最接近你希望形成的 Platform Owner 能力，也更适合支持你向 €90k–€120k 的云数据平台、Lakehouse 和 AI Platform 岗位发展。