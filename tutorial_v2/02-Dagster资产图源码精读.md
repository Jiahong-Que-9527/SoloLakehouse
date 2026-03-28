# 02 Dagster资产图源码精读

## 核心结论

v2 的“业务编排事实”集中在 `dagster/assets.py` 与 `dagster/definitions.py`。你必须能从这两个文件讲清楚资产、依赖、调度、检查、传感器。

---

## `dagster/assets.py`：资产定义层

### Bronze 资产

- `ecb_bronze`
  - 调用 `ECBCollector.collect()`
  - 配置 `RetryPolicy(max_retries=3, delay=5)`
  - 输出 metadata：`valid_count/rejected_count/path/rejected_path`
- `dax_bronze`
  - 调用 `DAXCollector.collect()`
  - 同样 Bronze 重试策略

**面试点**：Bronze 允许重试是因为上游采集常受网络和外部 API 波动影响。

### Silver 资产

- `ecb_silver` / `dax_silver`
  - 依赖对应 Bronze 资产输出
  - 调用 transformation 的 `run()` 写 Silver parquet
  - 读取结果 parquet 回填 `row_count` metadata

**面试点**：Silver 主要是确定性转换，通常不配自动重试，避免重复失败浪费资源。

### Gold / ML 资产

- `gold_features`
  - 依赖 `ecb_silver` 和 `dax_silver`
  - 生成事件研究特征数据
- `ml_experiment`
  - 依赖 `gold_features`
  - 调用 `run_experiment_set` 进行参数组合实验

---

## 传感器与资产检查（治理能力）

### `ecb_data_freshness_sensor`

- 每 30 分钟执行一次（`minimum_interval_seconds=1800`）
- 检查 `bronze/ecb_rates/` 最新分区日期
- 滞后 >= 48 小时时触发 `ecb_bronze` 重采集

**面试价值**：这是“数据可用性”治理，不是业务逻辑；体现平台思维。

### `gold_features_min_rows_check`

- 检查 `gold_features` 行数是否 >= 10
- 失败返回 `AssetCheckResult(passed=False)`

**面试价值**：把质量门禁绑定到资产生命周期，避免“下游 silent failure”。

---

## `dagster/definitions.py`：装配层

你要记住四件事：

1. `all_assets`：所有资产注册点
2. `full_pipeline_job`：通过 `define_asset_job` 选择资产集
3. `daily_pipeline_schedule`：`0 6 * * 1-5`（UTC）
4. `defs = Definitions(...)`：集中挂载 assets/jobs/schedules/sensors/checks/resources

---

## 一句话解释 asset-oriented 的优势

“资产编排把关注点从‘步骤执行顺序’转到‘数据产物依赖’，因此重跑、追踪、质量控制都更自然。”

---

## 面试追问：为什么还要 metadata？

回答框架：

- 可观测：行数、路径、拒绝记录数是快速诊断入口
- 可审计：资产输出事实可回放
- 可运营：异常时可快速定位“采集失败 vs 转换失败 vs 质量失败”
