# v1 Demo Runbook（从零开始，完整展示）

## 目标

这份文档让你在一台全新环境中，按固定步骤 **稳定演示 v1 全部核心能力**：

- 一键部署
- 健康检查
- 端到端数据/特征/ML流程
- SQL查询验证
- MLflow实验验证
- 重启后数据保留

---

## 0. 演示前准备（2分钟）

### 环境要求

- Docker + Docker Compose
- Python 3.11+
- `make`
- 可访问互联网（拉镜像 + ECB API）

### 讲解开场模板

“我先演示 v1 基线能力：5个核心服务、Medallion 数据流、ML 实验闭环。  
重点是它能从零部署、自动校验、稳定跑通，并且数据重启不丢。”

---

## 1. 从零初始化（3分钟）

在项目根目录执行：

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

然后启动：

```bash
make setup
```

### 你要讲的点

- `make setup` 会检查 Docker、准备 `.env`、拉镜像、启动服务并等待健康
- 这是“低门槛可复现”的关键设计

---

## 2. 健康检查（2分钟）

```bash
make verify
```

预期：核心服务都为 PASS（MinIO / PostgreSQL / Hive / Trino / MLflow）。

### 你要讲的点

- 不是“容器启动就算成功”，而是服务级可用性验证
- 这是交付可运维性的基本要求

---

## 3. 运行 v1 主流程（4分钟）

> v1 演示请使用兼容模式，确保口径一致

```bash
make pipeline-v1
```

（等价于 `make pipeline PIPELINE_MODE=v1`）

### 你要讲的点

流程共 6 步：

1. ECB 采集写 Bronze
2. DAX 采集写 Bronze
3. ECB 清洗到 Silver
4. DAX 清洗到 Silver
5. Silver 合并到 Gold 特征
6. ML 实验记录到 MLflow

强调“这是一条端到端闭环，不是孤立脚本”。

---

## 4. 展示“结果已落地”（4分钟）

### 4.1 Trino 查询 Gold 特征

```bash
docker exec -it slh-trino trino
```

在 Trino CLI 执行：

```sql
SHOW SCHEMAS IN hive;
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
```

### 4.2 MLflow 展示实验

浏览器打开：

- `http://localhost:5000`

展示 `ecb_dax_impact` 实验及运行记录。

### 4.3 MinIO 展示分层数据

浏览器打开：

- `http://localhost:9001`

展示 `bronze/`、`silver/`、`gold/` 路径。

---

## 5. 展示“重启不丢数据”（2分钟）

```bash
make down
make up
make verify
```

再次执行 Trino 查询，确认 Gold 数据仍在。

### 你要讲的点

- 这是“运行稳定性 + 数据持久化”证据
- 对平台工程师面试非常加分

---

## 6. 兜底预案（现场故障时）

### ECB 超时

```bash
make pipeline-v1
```

重试通常恢复。

### 某服务未就绪

```bash
make verify
make down
make up
```

### 彻底重置

```bash
make clean
make setup
```

---

## 7. 演示收尾话术（30秒）

“v1 我重点展示了三件事：  
第一，能从零稳定部署并验证；  
第二，数据到特征到实验的闭环能跑通；  
第三，重启后数据持续可用。  
这构成了 v2 平台化升级的可靠基线。”
