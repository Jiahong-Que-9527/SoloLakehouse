# SoloLakehouse 30-Min Demo Runbook

> 目标：部署后按流程演示每个部件功能，覆盖数据采集、分层存储、SQL 查询、ML 跟踪、编排治理。
>
> 适用版本：v2（当前主路径）+ v2.5（可选扩展）

---

## Demo Overview

- **总时长**：30 分钟
- **主线**：`部署验证 -> 运行 pipeline -> Dagster -> MinIO -> Trino -> MLflow -> 扩展能力`
- **主命令**：
  - `make up` / `make setup`
  - `make verify`
  - `make pipeline`
- **主要 UI**：
  - MinIO: `http://localhost:9001`
  - Trino: `http://localhost:8080`
  - MLflow: `http://localhost:5000`
  - Dagster: `http://localhost:3000`

---

## 0) 演示前准备（建议提前完成）

- 本地已安装 Docker + Compose + Python + make
- 仓库根目录存在 `.env`（可由 `.env.example` 复制）
- 已完成镜像拉取（避免演示时等待）
- 如果需要展示可选扩展：
  - OpenMetadata: `make up-openmetadata`
  - Superset: `make up-superset`

---

## 1) 30 分钟 Runbook（时间轴）

### 1.1 开场定位（1 分钟）

- **要点**
  - SoloLakehouse 是可本地完整运行的 Lakehouse 参考实现
  - 当前主路径是 v2 Dagster 编排，v1 路径保留兼容回退
  - 目标是演示“从数据到治理”的闭环

### 1.2 部署与健康检查（4 分钟）

- **命令**
  - `make up`（首次可用 `make setup`）
  - `make verify`
- **预期结果**
  - MinIO / PostgreSQL / Hive Metastore / Trino / MLflow / Dagster 均 `PASS`
- **讲解重点**
  - 平台不是“容器启动即可”，而是“健康检查通过后才算 ready”

### 1.3 运行主流程（3 分钟）

- **命令**
  - `make pipeline`
- **预期结果**
  - 结束日志出现 `RUN_SUCCESS`
- **讲解重点**
  - pipeline 逻辑：ECB + DAX -> Bronze -> Silver -> Gold -> ML Experiment

### 1.4 Dagster 编排治理（6 分钟）

- **入口**
  - 打开 `http://localhost:3000`
- **演示动作**
  - `Assets -> Asset Graph`：展示 6 个资产依赖关系
  - 点击 `gold_features`：查看资产元数据
  - `Runs`：查看本次执行日志
  - `Deployments -> Schedules`：查看 `daily_pipeline_schedule`
  - `Deployments -> Sensors`：查看 `ecb_data_freshness_sensor`
  - `Assets -> Asset Checks`：查看 `gold_features` 检查结果
- **讲解重点**
  - v2 的关键价值是可编排、可观测、可重跑、可治理

### 1.5 MinIO 分层数据（4 分钟）

- **入口**
  - 打开 `http://localhost:9001`
- **演示路径**
  - `sololakehouse/bronze/`
  - `sololakehouse/silver/`
  - `sololakehouse/gold/`
  - `sololakehouse/bronze/rejected/`
- **讲解重点**
  - Bronze 按日期分区且不可变
  - 校验失败记录进入 rejected 路径，不会静默丢失

### 1.6 Trino 查询能力（4 分钟）

- **命令**
  - `docker exec -it slh-trino trino`
- **SQL**
  - `SHOW CATALOGS;`
  - `SHOW SCHEMAS IN hive;`
  - `SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;`
- **可选（v2.5）**
  - `SELECT * FROM iceberg.gold.ecb_dax_features_iceberg LIMIT 10;`
- **讲解重点**
  - Gold 层可以被 SQL 用户直接消费，支持分析与下游 BI

### 1.7 MLflow 实验跟踪（4 分钟）

- **入口**
  - 打开 `http://localhost:5000`
- **演示动作**
  - 进入实验 `ecb_dax_impact`
  - 展示参数（模型与超参）
  - 展示指标（RMSE/MAE）
  - 展示 artifacts（模型文件）
- **讲解重点**
  - 训练结果可追溯、可对比、可复现

### 1.8 收尾与扩展（4 分钟）

- **兼容路径（可选）**
  - `make pipeline-v1`
- **扩展能力（可选）**
  - `make up-openmetadata`
  - `make up-superset`
- **讲解重点**
  - v2 是主路径，v1 是回退保障
  - v2.5 展示生态扩展能力，不改变主线定位

---

## 2) 主持人脚本版（逐段可直接念）

### 2.1 开场白（约 60 秒）

“今天我会用 30 分钟演示 SoloLakehouse 的完整流程。  
它不是一个库，而是一个可本地运行的 Lakehouse 参考平台。  
我们会从部署开始，跑通数据 pipeline，然后依次看 Dagster 编排、MinIO 分层存储、Trino SQL 查询、MLflow 实验跟踪，最后补充 v1 兼容路径和 v2.5 可选扩展能力。”

### 2.2 部署与健康检查讲解词

“我先启动平台并做健康检查。  
这里我们关注的不只是容器是否启动，而是服务是否真的可用。  
当 `make verify` 显示 6 个核心服务都是 PASS，才说明平台就绪，可以进入业务流程演示。”

### 2.3 运行 pipeline 讲解词

“现在我触发默认的 v2 pipeline。  
它会按资产依赖执行 ECB 和 DAX 数据处理链路，从 Bronze 到 Silver，再到 Gold 和 ML 实验。  
看到 `RUN_SUCCESS` 就代表这次端到端流程成功完成。”

### 2.4 Dagster 讲解词

“接下来是编排层。  
在 Asset Graph 里可以看到 6 个软件定义资产及依赖关系。  
这意味着我们可以精确追踪每个资产的状态和血缘，也可以按资产粒度重跑，不需要每次从头跑整条链路。  
此外，这里还有 schedule、sensor 和 asset check，体现了平台的运营治理能力。”

### 2.5 MinIO 讲解词

“这里是存储层。  
可以看到 Bronze、Silver、Gold 三层目录，以及 rejected 路径。  
这说明数据不仅有分层治理，还有异常记录留存，避免坏数据被静默丢弃。”

### 2.6 Trino 讲解词

“接下来用 Trino 做 SQL 查询。  
先看 catalog 和 schema，再直接查 Gold 特征表。  
这一步证明平台产出的特征数据已经可以被标准 SQL 工具消费，方便分析和下游应用接入。”

### 2.7 MLflow 讲解词

“最后看 MLflow。  
这里可以看到每次训练的参数、指标和模型产物。  
这让实验过程具备可追溯、可比较能力，而不是只得到一个孤立模型文件。”

### 2.8 结束语（约 60 秒）

“总结一下，这个项目已经具备从采集、加工、查询到实验跟踪和编排治理的端到端闭环。  
当前主路径是 v2 的 Dagster 化运营模式，v1 路径保留回退，v2.5 提供了 Iceberg/OpenMetadata/Superset 的可选扩展。  
下一步如果走向生产化，就进入 v3 的多环境、治理、安全和 SLO 可观测性建设。”

---

## 3) 现场防翻车清单

- 演示开始前先执行一次 `make verify`
- `Dagster` 若未就绪，等待 60-90 秒后重试 `make verify`
- Trino 若查不到 Gold 表，确认 `make pipeline` 成功后重跑一次
- 演示过程中避免执行 `make clean`（会删除 volumes）
- 可选扩展如果不稳定，不影响主链路演示，优先保主流程完整

---

## 4) 命令速查（演示专用）

```bash
# 启动与验证
make up
make verify

# 运行主流程（v2）
make pipeline

# 可选：v1 兼容路径
make pipeline-v1

# Trino CLI
docker exec -it slh-trino trino

# 可选扩展
make up-openmetadata
make verify-openmetadata
make up-superset
make verify-superset
```

---

## 5) 附：30 秒版本介绍（电梯稿）

“SoloLakehouse 是一个本地可完整运行的 Lakehouse 参考平台。  
它已经实现从数据采集、分层加工、SQL 查询到 ML 实验跟踪的闭环，并通过 Dagster 提供资产级编排、调度、检查和可视化运维。  
当前适合内部 MVP 和教学展示，后续将通过 v3 完成生产级治理与多环境硬化。”

---

## 6) 10 分钟精简版（快演示）

> 适用于时间紧、只展示核心价值的场景。  
> 原则：只保留“平台就绪 -> 跑通 -> 可视化治理 -> 数据可消费”四件事。

### 6.1 时间轴（10 分钟）

- **第 1 分钟：开场**
  - 目标：演示从数据到治理的闭环，主路径是 v2 Dagster
- **第 2-3 分钟：平台就绪**
  - 命令：`make verify`
  - 强调 6 个核心服务 `PASS`
- **第 4-5 分钟：触发主流程**
  - 命令：`make pipeline`
  - 强调成功标志 `RUN_SUCCESS`
- **第 6-7 分钟：Dagster 编排价值**
  - UI：`http://localhost:3000`
  - 看 `Asset Graph` + `Runs` + `Schedule`
- **第 8 分钟：数据落地**
  - UI：`http://localhost:9001`
  - 看 Bronze/Silver/Gold 和 rejected
- **第 9 分钟：SQL 消费**
  - 命令：`docker exec -it slh-trino trino`
  - SQL：`SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;`
- **第 10 分钟：收尾**
  - MLflow 一眼展示：`http://localhost:5000`
  - 结论：平台已具备编排治理 + 数据可消费 + 实验可追溯

### 6.2 10 分钟最小命令集

```bash
make verify
make pipeline
docker exec -it slh-trino trino
```

在 Trino CLI 中执行：

```sql
SHOW SCHEMAS IN hive;
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
```

### 6.3 10 分钟主持人脚本（可直接念）

“我用 10 分钟展示 SoloLakehouse 的核心闭环：先确认平台服务健康，再触发 v2 的 Dagster 编排流程。  
当 pipeline 成功后，我们在 Dagster 看到资产依赖和运行记录，在 MinIO 看到 Bronze/Silver/Gold 分层落地，在 Trino 直接查询 Gold 特征表，在 MLflow 查看实验参数和指标。  
这说明平台不仅能跑通流程，还具备可视化治理和可追溯能力。”

### 6.4 精简版防翻车提示

- 若 `make verify` 有 `TIMEOUT`，先等 60 秒再重试
- 若 `make pipeline` 未成功，不要继续 UI 演示，先保证主流程成功
- 若 Trino 查不到 Gold 表，重跑一次 `make pipeline`
