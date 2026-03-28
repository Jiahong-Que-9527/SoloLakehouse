# 06 transformations 源码精读

## 模块清单

- `transformations/ecb_bronze_to_silver.py`
- `transformations/dax_bronze_to_silver.py`
- `transformations/silver_to_gold_features.py`
- `transformations/quality_report.py`

## ECB Bronze -> Silver

- 将 `observation_date` 转成日期类型。
- `rate_pct` 数值化并前向填充。
- 计算 `rate_change_bps = (rate_pct - shift(1)) * 100`。
- 删除 metadata 列，输出显式字段子集。

## DAX Bronze -> Silver

- OHLCV 强制数值化。
- 周末过滤（`dayofweek < 5`）。
- 计算 `daily_return`。
- 去重并输出固定列顺序。

## Silver -> Gold 特征工程

- 仅保留 ECB 实际变动事件（`rate_change_bps != 0`）。
- 事件日与 DAX 交易日对齐（向后最多 3 天）。
- 构建 1 日收益、5 日累计收益、事件前 5 日波动等特征。

## `run_silver_quality_report` 的价值

- 不中断流程，但输出关键质量度量：行数、空值、日期范围、重复。
- 在实际平台里可映射到告警/看板。

## 面试讲法（2 分钟）

“我把转换层做成纯函数 + I/O orchestration 双层结构。纯函数保证可测试和可复用，run 函数处理 MinIO 读写。这样后续改编排器（比如 Dagster）时，可以复用核心业务逻辑而不是重写整层代码。”
