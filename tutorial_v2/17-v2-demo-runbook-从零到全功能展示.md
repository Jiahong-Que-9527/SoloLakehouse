# v2 Demo Runbook（从零开始，展示全部能力）

## 目标

这份文档用于完整演示 v2 平台能力，确保你能流畅展示：

- v2 默认编排（Dagster）
- v1 兼容编排（legacy）
- 资产依赖与可视化
- 调度/传感器/资产检查
- 失败定位与重跑
- 发布级口径（文档、决策、历史闭环）

---

## 总时长建议

- 标准版：30分钟
- 快速版：20分钟（跳过可选步骤）

---

## 0. 演示前准备（3分钟）

### 环境要求

- Docker + Compose
- Python 3.11+
- `make`
- 浏览器可访问本地端口

### 开场话术

“我接下来演示 v2：默认用 Dagster 资产编排，但保留 v1 兼容路径。  
这体现了平台升级中的稳态迁移策略：新能力上线，同时保留回退方案。”

---

## 1. 从零启动（4分钟）

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dagster.txt
make setup
```

### 验证服务

```bash
make verify
```

### 你要强调

- v2 服务包含 Dagster（webserver/daemon）
- 平台依旧保留低门槛本地部署体验

---

## 2. 默认路径：v2 Dagster 编排（5分钟）

```bash
make pipeline
```

### 你要强调

- 这是 v2 默认入口
- 背后执行 `full_pipeline_job`
- 资产链路覆盖 Bronze/Silver/Gold/ML 全流程

---

## 3. 可视化展示（Dagster UI）（5分钟）

打开：

- `http://localhost:3000`

演示顺序：

1. Assets 页面看到 6 个核心资产
2. 点开 `gold_features` 查看上游依赖
3. 在 Runs 页面查看本次执行状态与事件
4. 查看 Asset Checks（`gold_features` 行数检查）

### 讲解要点

- v1 是“脚本日志主导”
- v2 是“资产视角 + 可视化治理”

---

## 4. 调度与自动化治理（4分钟）

在 UI 中演示：

1. Schedules 页面找到 `daily_pipeline_schedule`
2. 展示 cron（工作日 06:00 UTC）
3. Sensors 页面展示 `ecb_data_freshness_sensor`

### 讲解要点

- 传感器解决“数据新鲜度”问题，不是仅仅跑定时任务
- 编排系统从“执行”升级为“治理”

---

## 5. 兼容路径：v1 风格执行（3分钟）

```bash
make pipeline-v1
# 或 make pipeline PIPELINE_MODE=v1
```

### 讲解要点

- 这证明升级不是硬切换
- 面向迁移期与演示场景，回退路径明确

---

## 6. 数据与ML结果验证（4分钟）

### Trino 查询 Gold

```bash
docker exec -it slh-trino trino
```

```sql
SELECT * FROM hive.gold.ecb_dax_features LIMIT 10;
```

### MLflow 查看实验

- `http://localhost:5000`
- 展示 `ecb_dax_impact` 运行记录

### MinIO 查看分层产物

- `http://localhost:9001`
- 展示 Bronze/Silver/Gold 路径

---

## 7. 故障演示（可选加分，3分钟）

### 场景：某次作业失败后如何恢复

演示口述即可（或现场模拟）：

1. 先看服务健康 `make verify`
2. 在 Dagster Runs 看失败资产
3. 定位日志与输入数据
4. 资产级重跑（而非全量）

### 讲解要点

- 这是平台工程能力，不是脚本工程能力

---

## 8. 发布治理与文档闭环（2分钟）

展示以下文档路径（无需逐行）：

- `docs/roadmap.md`
- `docs/v1-to-v2-transition.md`
- `docs/decisions/ADR-006-v2-dagster-orchestration.md`
- `docs/history/timeline.md`

### 讲解要点

- 代码、决策、历史、发布文档一致
- 版本演进可追溯，适合团队协作和面试审查

---

## 9. 收尾话术（30秒）

“v2 我展示了默认 Dagster 编排、可视化治理、质量检查与数据新鲜度控制，同时保留 v1 兼容执行路径。  
这说明项目不是单纯功能迭代，而是一次可回滚、可运营、可解释的平台化升级。”

---

## 附录：一键命令清单（备忘）

```bash
make setup
make verify
make pipeline
make pipeline-v1
make down
make up
```

UI:

- Dagster: `http://localhost:3000`
- MLflow: `http://localhost:5000`
- MinIO: `http://localhost:9001`
