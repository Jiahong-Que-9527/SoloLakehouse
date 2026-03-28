# 05 ingestion 源码精读

## 关键文件

- `ingestion/collectors/ecb_collector.py`
- `ingestion/collectors/dax_collector.py`
- `ingestion/bronze_writer.py`
- `ingestion/quality/bronze_checks.py`
- `ingestion/schema/*`

## ECBCollector 流程

1. `_fetch_data()`：请求 ECB API，3 次重试，失败抛 `CollectorUnavailableError`。  
2. `_validate_records()`：Pydantic 校验，分成 `valid` 与 `rejected`。  
3. `run_ecb_bronze_checks()`：校验日期与 schema 等约束。  
4. `BronzeWriter.write()`：写 `bronze/ecb_rates/...`。  
5. `write_rejected()`：写 rejected 分区。  

### 亮点

- 增量策略：`_already_ingested_today()` 防止重复采集。
- 可强制重跑：`--force` 由 pipeline 透传。
- 日志结构化：可直接被后续日志系统消费。

## DAXCollector 流程

- 读取本地 CSV 后进行列重命名并复用同样的 validate/check/write 逻辑。
- 结构与 ECBCollector 对齐，便于扩展新数据源时复用模式。

## BronzeWriter 设计

- 写入统一使用 PyArrow + snappy Parquet。
- 路径规范固定，保证下游可预测读取。
- `write_rejected` 强制 `rejection_reason` 非空，避免“有坏数据但无原因”。

## 面试深挖点

### 为什么 rejected 不是直接丢弃

- 丢弃会损失可观测性和可修复性。
- rejected 为数据供应方治理和 schema 演进提供事实基础。

### 为什么增量检测按分区而不是按记录 hash

- 这是 v1 的低复杂度折中：按天分区符合批处理语义。
- 记录级去重可作为 v2/v3 的增强策略。
