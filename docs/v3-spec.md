# SoloLakehouse v3 Spec

## 目标

将 SoloLakehouse 从：

> v2：面向内部 MVP 的 Dagster 编排型 Lakehouse 平台

升级为：

> v3：具备生产化部署、治理、可观测性与发布控制能力的平台参考实现

---

## 核心原则

v3 的重点不是继续扩展数据功能，而是补齐平台能力。

优先级如下：

1. 多环境可复现部署
2. 治理与安全基线
3. 可观测性与可靠性
4. 发布、回滚与运维流程

一句话概括：

> Focus on platform productionization, not feature expansion.

---

## v3 的范围边界

### 应该优先做

- 基于 Kubernetes / Helm / Terraform 的多环境部署基线
- `dev -> staging -> production` 的环境晋升与回滚机制
- secrets lifecycle、least privilege、access auditability
- SLO 驱动的 metrics、alerting、dashboard、runbook
- 数据集治理约定：owner、refresh SLA、quality class、lineage responsibility
- 实验平台层面的 ML 治理与可追踪性增强

### 不应在 v3 里扩张为主线

- 不把项目做成完整 Databricks / Snowflake 替代品
- 不优先引入 Kafka、Flink 等复杂分布式系统
- 不以“新增更多业务数据源/分析功能”为目标
- 不把完整在线 serving 平台作为 v3 必选项
- 不把自助式产品化 UI/门户作为 v3 主交付

---

## 必需能力域

## 1. Infrastructure & Environment Promotion

### 目标

- 支持多环境一致部署
- 建立可验证的晋升链路
- 保证发布可回滚

### 要求

- 引入 Kubernetes manifests 或 Helm chart skeleton
- 引入 Terraform baseline 管理基础设施依赖
- 明确环境链路：
  - `dev`
  - `staging`
  - `production`
- 每次环境晋升必须经过：
  - 部署成功与健康检查
  - pipeline 执行成功
  - 测试 / lint / typecheck / runtime quality gate
  - rollback readiness 验证

### 说明

本项目的 v3 环境治理重点是 **promotion model**，不是简单增加 `.env.dev` / `.env.prod` 文件。

---

## 2. Security & Access Governance

### 目标

- 从本地开发风格的凭据管理，升级到生产化治理模型

### 要求

- 逐步摆脱生产环境对静态 `.env` 的依赖
- 引入受管理的 secrets 来源与注入方式
- 定义 least-privilege service credentials
- 记录 access change 的审计证据
- 提供 secrets rotation / emergency fallback 的运行说明

### 说明

v3 的重点是 **服务级别安全治理**，不是先做面向终端用户的完整认证产品。

---

## 3. Reliability & Observability

### 目标

- 让系统从“能排查”走向“可量化运营”

### 要求

- 定义关键 SLO
- 为关键链路建立指标：
  - orchestration success rate
  - pipeline freshness
  - ingestion / pipeline latency
  - data quality pass rate
- 建立 alert rules，并与 SLO breach 对齐
- 提供 dashboard 作为统一运行视图
- 补齐 incident runbooks，并至少做基础 drill

### 说明

Prometheus / Grafana 可以作为实现方案，但本项目 v3 更强调 **SLO-driven operations**，而不是“为了上工具而上工具”。

---

## 4. Data Governance Baseline

### 目标

- 让关键数据集具备可发现、可说明、可负责的治理基线

### 要求

- 保持 **Hive-first catalog strategy**
- 不在 v3 强制切换到新的 catalog 平台
- 为关键 Gold 与核心 Silver 数据集补齐治理元数据：
  - `data_owner`
  - `refresh_sla`
  - `quality_class`
  - lineage responsibility
- 定义跨环境的 schema / table / storage prefix naming conventions

### 说明

v3 的数据治理重点是 **标准化和 upgrade-ready**，不是立即集成 OpenMetadata / DataHub 这类更重的目录平台。

---

## 5. ML Boundary for v3

### 目标

- 保持数据平台到 ML 的叙事连续性
- 控制范围，避免 serving 方向过早膨胀

### 要求

- 强化训练 / 评估流程的可复现性
- 强化 experiment metadata、artifact lineage、evaluation contract
- 保持 MLflow 作为实验追踪核心组件
- 为未来 serving 留好接口，但不把完整 serving platform 设为 v3 必须项

### 说明

v3 是 **experiment platform first**，不是 full ML productization。

---

## 6. Release & Operations Model

### 目标

- 让发布从“能发”升级为“可控、可审计、可回滚”

### 要求

- CI/CD 持续执行：
  - tests
  - lint
  - type check
- 建立 release gates
- 建立 rollback 标准流程
- 发布记录与变更证据要可追踪
- 更新 release checklist、history、ADR 索引与版本状态文档

---

## 现阶段不作为 v3 Required 的内容

- 完整在线推理 serving 平台
- Superset / FastAPI 作为核心主线交付
- Keycloak 级别的完整身份系统
- OpenMetadata / DataHub 的强制接入
- 复杂流式架构

这些内容可以作为：

- later phase
- v4 候选项
- 或在明确场景驱动下单独立项

---

## v3 预期结果

最终的 SoloLakehouse v3 应该表现为：

> 一个面向生产化思维的小型 Lakehouse 平台参考实现

它应具备：

- 多环境可复现部署能力
- 明确的环境晋升与回滚流程
- 基础的 secrets / access / governance 控制
- SLO 驱动的可观测性与运维基线
- 可审计的发布流程
- 面向实验平台的 ML 治理延续性

---

## v3 最终定义

> A production-capable, governance-ready, observable Solo Lakehouse platform with controlled ML experiment integration.

---

## v3 Task Graph

下面这部分不是概念说明，而是面向实施的推进顺序。

### Workstream 1: Infrastructure Baseline

目标：先把 v3 的“骨架”搭出来，让多环境部署从文档目标变成工程对象。

- 建立 Kubernetes manifests 或 Helm chart skeleton
- 为核心服务与 Dagster 服务设计部署结构
- 补齐 `dev` 与 `staging` 的环境分层方式
- 引入 Terraform baseline 管理基础设施依赖
- 明确本地 Compose 路径与 v3 infra 路径的并存关系

完成标志：

- 同一版本可以在 `dev` 与 `staging` 用一致工件部署
- 部署步骤可复现、可验证、可回滚

### Workstream 2: Promotion & Release Controls

目标：把“发布”变成有 gate 的流程，而不是一次性操作。

- 固化 `dev -> staging -> production` promotion flow
- 定义每次 promotion 的验证项
- 补齐 rollback checklist 与 release evidence
- 把 release checklist 与 history / ADR / changelog 更新动作纳入流程

完成标志：

- 至少完成一次端到端 staged release 演练
- promotion 和 rollback 都有文档和验证记录

### Workstream 3: Secrets & Access Governance

目标：把 v2 的本地开发型凭据模型升级为最小生产治理基线。

- 定义 secrets source 与 runtime injection pattern
- 识别关键服务的凭据边界
- 建立 least-privilege service credentials 模型
- 记录 access change 的审计要求
- 编写 rotation 与 emergency fallback runbook

完成标志：

- 关键服务不再依赖生产静态 `.env`
- access change 可以留下审核与执行证据

### Workstream 4: Observability & Reliability

目标：从“出问题再查”升级为“主动监控与预警”。

- 定义关键 SLO
- 为成功率、freshness、latency、quality pass rate 建立指标
- 建立 alerts 与 dashboards
- 补齐 incident 分类和恢复 runbook
- 至少做基础 drill，验证告警与处置链路

完成标志：

- 有最小可用 dashboard
- 有关键告警
- 有至少一次 runbook drill 记录

### Workstream 5: Data Governance Baseline

目标：先把治理约定立住，而不是急着换目录系统。

- 为关键 Gold 与核心 Silver 输出定义治理合同
- 补齐 `data_owner`、`refresh_sla`、`quality_class`
- 明确 lineage responsibility
- 统一环境间 schema、table、storage prefix 命名规则

完成标志：

- 核心数据集存在明确治理元数据
- 命名与 ownership 规则可被团队直接遵循

### Workstream 6: ML Experiment Governance

目标：延续 ML 叙事，但控制在实验平台边界内。

- 强化训练 / 评估流程的可复现性
- 统一 experiment metadata 与 artifact 路径约定
- 明确 evaluation contract
- 为未来 serving 预留接口，但不实现完整 serving 平台

完成标志：

- MLflow 运行记录更完整、可追踪
- 模型实验与数据资产之间的关系更可解释

---

## Recommended Execution Order

建议按下面顺序推进：

1. Infrastructure Baseline
2. Promotion & Release Controls
3. Secrets & Access Governance
4. Observability & Reliability
5. Data Governance Baseline
6. ML Experiment Governance

原因很简单：

- 先有多环境与部署骨架，后面的治理和运维才有承载面
- 先把 release / rollback 立起来，后续改动才可控
- 数据治理和 ML 治理应该建立在稳定的平台骨架之上

---

## For Code Agent

下面这段是更短、更适合直接喂给 code agent 的版本。

### SoloLakehouse v3 Prompt

You are working on SoloLakehouse v3.

The project is currently at:

- v1 delivered
- v2 current: Dagster-orchestrated internal MVP platform
- v3 planned: production-capable platform hardening

Your job is to improve **platform productionization**, not expand product features.

Priorities:

1. Multi-environment reproducibility
2. Promotion and rollback controls
3. Secrets and access governance
4. SLO-driven observability and incident operations
5. Hive-first governance baseline
6. ML experiment governance, not full serving

Important constraints:

- Do not expand scope into Kafka, Flink, or complex distributed systems
- Do not treat FastAPI, Superset, or online serving as required v3 deliverables
- Do not force OpenMetadata or DataHub adoption in v3
- Do not replace the current Hive-first baseline unless explicitly requested
- Preserve compatibility with current v2 semantics where possible

Expected v3 outcome:

- reproducible deployment across environments
- `dev -> staging -> production` promotion flow
- rollback readiness
- managed secrets direction
- least-privilege access baseline
- SLO-backed metrics, alerts, dashboards, runbooks
- dataset governance contracts for key Gold and critical Silver outputs
- stronger ML experiment lineage and reproducibility

When making decisions, prefer:

- maintainable patterns over maximal complexity
- governance clarity over tool-chasing
- upgrade-ready architecture over premature platform replacement
- production-minded operations over feature expansion

---

## 一句话版

如果要把 v3 的主线压缩成一句话，可以直接用：

> SoloLakehouse v3 的目标不是“做更多功能”，而是把现有平台升级成一个具备多环境、治理、安全、可观测性与发布控制能力的生产化参考实现。
