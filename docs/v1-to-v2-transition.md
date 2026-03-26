# v1 到 v2 迁移总览

## 目的

本文档用于完整描述 SoloLakehouse 的三个关键状态：

- **v1（已交付）**：五服务核心 Lakehouse 基线
- **v1 -> v2（迁移过程）**：从线性脚本编排到资产编排
- **v2（当前）**：Dagster 驱动的可调度、可治理、可回放平台形态

---

## 1. v1（已交付）基线能力

### v1 核心组件

- MinIO（对象存储）
- PostgreSQL（元数据后端）
- Hive Metastore（表元数据）
- Trino（查询引擎）
- MLflow（实验跟踪）

### v1 运行主路径

- `scripts/run-pipeline.py` 线性执行 6 步：
  1. ECB Ingestion
  2. DAX Ingestion
  3. ECB Bronze -> Silver
  4. DAX Bronze -> Silver
  5. Silver -> Gold
  6. ML Experiment

### v1 交付重点

- Ingestion 容错（重试、异常包装、拒绝记录）
- Medallion 数据层（Bronze/Silver/Gold）
- 单机可复现部署（`make up` / `make verify` / `make pipeline`）
- CI 质量门禁（lint/typecheck/test/coverage）

---

## 2. 为什么从 v1 演进到 v2

v1 的瓶颈不在“能否跑通”，而在“平台可运营性”：

- 调度能力薄弱（脚本定时可做，但缺乏平台语义）
- 资产级可视化不足（依赖关系与重跑范围不直观）
- 运行治理不足（需要框架级 sensor/check）

因此 v2 的目标是：

- 建立资产编排语义（asset-first）
- 建立调度与自动化治理能力
- 保持本地低门槛和迁移回滚能力

---

## 3. v1 -> v2 的迁移策略

### 策略原则

1. **先平台化编排，再深改业务逻辑**
2. **保留 legacy 回退路径，降低一次切换风险**
3. **文档与历史同步升级，确保版本叙事连续**

### 迁移落地点

- 新增 Dagster 项目结构：
  - `dagster/assets.py`
  - `dagster/resources.py`
  - `dagster/definitions.py`
  - `dagster/workspace.yaml`
  - `dagster/dagster.yaml`
  - `dagster/io_managers.py`（可选增强，已实现）
- 新增 Dagster 运行服务：
  - `dagster-webserver`
  - `dagster-daemon`
- 新增 PostgreSQL 数据库：
  - `dagster_storage`
- 默认执行入口切换：
  - `make pipeline` -> Dagster job
  - `make pipeline-legacy` -> 旧脚本

---

## 4. v2（当前）能力说明

### 资产图

```text
ecb_bronze      dax_bronze
    |               |
ecb_silver      dax_silver
      \           /
       \         /
        gold_features
              |
         ml_experiment
```

### 编排与治理

- `full_pipeline_job`：完整资产链路执行
- `daily_pipeline_schedule`：工作日 06:00 UTC
- `ecb_data_freshness_sensor`：ECB 数据新鲜度检测与触发
- `gold_features` asset check：最低行数质量门禁

### 运行与可运维性

- Dagster UI 可视化 run/asset/lineage
- 资产级重跑与失败定位
- 结构化时延指标：`pipeline.step.duration_ms`

---

## 5. 设计取舍与已知风险

### 已采纳取舍

- Dagster 作为 v2 编排框架（而非继续 script+cron）
- 迁移期保留 legacy 路径
- Dagster 运行历史存储使用 PostgreSQL（非 SQLite）

### 当前风险

- 双路径运行带来短期运维复杂度
- 仍是单机 Compose 参考实现，不是多环境生产架构

---

## 6. 如何在面试中表达 v1 -> v2

可直接复述：

“v1 解决了可部署、可跑通、可验证的问题；  
v2 解决了可编排、可治理、可回放的问题。  
我没有激进重写业务逻辑，而是把既有数据和 ML 模块资产化接入 Dagster，并保留 legacy 回退路径，保证迁移稳态。”

---

## 7. 相关文档

- 路线图：`docs/roadmap.md`
- 详细任务：`docs/EVOLVING_PLAN.md`
- Dagster 使用：`docs/DAGSTER_GUIDE.md`
- 历史时间线：`docs/history/timeline.md`
- 架构演进：`docs/history/architecture-evolution.md`
- 决策记录：`docs/decisions/`
