# Agent Prompt Reference

Prompts for working with AI coding agents on SoloLakehouse.
All prompts assume the agent has read `CLAUDE.md` and `TASKS.md` first.

---

## Implementation

### Start from scratch

```
读取 TASKS.md，从 Block 0 开始按顺序实现，完成一个任务标记一个 [x]，
完成整个 Block 后告诉我结果和下一步。
```

### Run a specific block

```
读取 TASKS.md，实现 Block 1（Docker 基础设施），
按顺序完成 B1-1 到 B1-8，每完成一个任务标记 [x]。
```

### Run a single task

```
读取 TASKS.md，实现任务 B2-6（ECBCollector）。
```

### Resume from a checkpoint

```
读取 TASKS.md，找到第一个未完成的任务（[ ]），从那里继续实现。
```

### Run multiple blocks at once

```
读取 TASKS.md，实现 Block 0 到 Block 2，
按顺序完成所有任务，完成一个标记一个。
```

---

## Verification

### Verify a block is correctly implemented

```
读取 TASKS.md，检查 Block 2（采集层）的所有任务是否已正确实现：
文件是否存在、函数签名是否符合规格、关键逻辑是否到位。
列出通过和不符合的项目。
```

### Check overall progress

```
读取 TASKS.md，扫描所有文件，
告诉我哪些任务已完成 [x]、哪些未完成 [ ]，给出当前进度百分比。
```

### Run tests after implementation

```
实现 Block 6（Tests）后运行 make test，
报告通过/失败情况，修复所有失败的测试。
```

---

## Fixing & Debugging

### Fix a failing test

```
运行 make test，找出失败的测试，
定位根本原因，修复代码（不是测试），再次运行确认通过。
```

### Fix lint errors

```
运行 make lint，修复所有 ruff 报告的问题，
不要改变代码逻辑，只修格式和 import 顺序。
```

### Fix type errors

```
运行 make typecheck，修复所有 mypy 报告的类型错误，
给缺少类型注解的 public 函数补充参数和返回值类型。
```

### Debug a pipeline failure

```
运行 make pipeline，如果失败，
定位失败的步骤，找出根本原因，修复后重新运行验证。
```

---

## Code Review

### Review a specific file

```
读取 ingestion/collectors/ecb_collector.py，
对照 CLAUDE.md 中的 Collector Pattern 和 TASKS.md B2-6 的规格，
报告不符合的地方，然后修复。
```

### Check patterns compliance

```
读取 ingestion/ 和 transformations/ 下的所有文件，
检查是否符合 CLAUDE.md 中定义的 Collector Pattern、
Transformation Pattern、Logging Pattern 和 MinIO I/O Pattern。
列出不符合的地方。
```

### Security check

```
检查所有 Python 文件，确认没有硬编码的密码、API key 或 endpoint，
所有凭据都通过 os.environ.get() 读取，且有合理的本地默认值。
```

---

## Specific Scenarios

### Pipeline runs but no Gold data

```
make pipeline 运行成功但 Gold 层没有数据，
检查 silver_to_gold_features.py 的 build_gold_features 函数，
确认 ECB 和 DAX 数据能正确 join，打印中间 DataFrame 的行数诊断问题。
```

### Add a new data source

```
参考 CLAUDE.md 的 Collector Pattern 和 TASKS.md B2-6/B2-7 的实现，
为 [新数据源名称] 添加一个新的 Collector：
- ingestion/schema/[source]_schema.py（Pydantic v2 model）
- ingestion/collectors/[source]_collector.py（Collector class）
- tests/test_schemas.py 中补充对应测试
```

### Regenerate sample data

```
重新生成 data/sample/dax_daily_sample.csv，
要求：500 行以上，交易日（无周末），日期从 2000-01-03 到 2024-12-31，
列名：date,open,high,low,close,volume，
价格范围 3000–20000，日波动 ±3%，high >= low，所有值 > 0。
```

### v1.0 release validation

```
按照 docs/V1_RELEASE_CHECKLIST.md 逐项验证，
每项运行对应命令，记录实际输出，标记 [x] 通过或 [ ] 失败，
最后给出总结和需要修复的项目。
```

---

## Useful Combinations

### Full implementation in one go (B0–B8, skip tagging)

```
读取 TASKS.md 和 CLAUDE.md。
按顺序实现 Block 0 到 Block 8 的所有任务（跳过 B9-5 打 tag）。
每完成一个任务标记 [x]。遇到阻塞告诉我，不要跳过。
```

### Implement + test a single layer

```
读取 TASKS.md，实现 Block 2（采集层）和对应的 Block 6 测试（B6-1 到 B6-3），
实现完一个模块立即写对应测试，最后运行 make test 确认全部通过。
```

### CI green check

```
依次运行 make lint、make typecheck、make test-cov，
修复所有错误直到三个命令全部通过，报告最终状态。
```
