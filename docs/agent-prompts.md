# Agent Prompt Reference

Prompts for working with AI coding agents on SoloLakehouse.
Agents should read `CLAUDE.md` first, then use:

- `docs/EVOLVING_PLAN.md` for active v2/v3 execution backlog
- `TASKS.md` for historical v1 implementation ledger

---

## Current Scope Prompts (v2/v3)

### Continue from latest backlog

```
读取 CLAUDE.md 和 docs/EVOLVING_PLAN.md，
从第一个未完成任务继续实现，完成后更新勾选状态并汇报影响文件。
```

### Execute v3 governance tasks

```
读取 docs/EVOLVING_PLAN.md 的 Phase 4，
优先实现治理相关任务（Task 67+），并同步更新 docs/governance-v3-matrix.md 证据链接。
```

### Harden production-readiness docs

```
对齐 docs/roadmap.md、docs/history/*、docs/decisions/*、docs/release*.md，
确保 v2 current、v3 planned 和 governance 术语一致。
```

### Keep dual pipeline compatibility

```
检查并维护 Makefile 的双模式：
- make pipeline（v2 default）
- make pipeline PIPELINE_MODE=v1 / make pipeline-v1（v1 compatibility）
更新对应文档说明。
```

---

## Verification Prompts

### Validate docs consistency

```
扫描 docs/ 目录，检查以下一致性：
1) 版本状态（v1 delivered, v2 current, v3 planned）
2) 默认命令与兼容命令
3) ADR 索引与实际文件
4) history/roadmap/evolving_plan 交叉引用
输出不一致清单并修复。
```

### Governance readiness review

```
读取 docs/governance-v3-matrix.md、docs/governance-v3-runbook.md、
docs/V3_RELEASE_CHECKLIST.md，评估哪些项已具备证据、哪些仅为计划。
输出高/中/低优先级缺口。
```

### CI quality gate check

```
依次运行 make lint、make typecheck、make test-cov，
修复失败项并汇报最终状态。
```

---

## Debugging Prompts

### Debug v2 default pipeline failure

```
运行 make pipeline，
如果失败，定位 Dagster 资产或服务依赖问题，
修复后重新运行并给出根因分析。
```

### Debug v1 compatibility pipeline failure

```
运行 make pipeline PIPELINE_MODE=v1，
如果失败，定位 scripts/run-pipeline.py 中失败步骤，
修复并验证兼容路径恢复。
```

### Diagnose data freshness/check failures

```
检查 Dagster sensor 与 asset check：
- ecb_data_freshness_sensor
- gold_features_min_rows_check
定位失败条件并输出修复建议。
```

---

## Architecture & Governance Review Prompts

### Review decision alignment

```
读取 docs/decisions/ADR-006 到 ADR-012，
检查是否与 docs/history/v3-planning.md 和 docs/EVOLVING_PLAN.md 任务一致，
列出决策与执行不一致项。
```

### Security/governance policy review

```
检查配置和代码中是否仍存在生产不建议模式：
- 静态凭据假设
- 过宽权限
- 缺少审计路径
结合 ADR-009 给出整改建议。
```

---

## Legacy / Historical Prompts (v1 ledger)

### Review v1 completion evidence

```
读取 TASKS.md 和 docs/V1_RELEASE_CHECKLIST.md，
核验 v1 交付证据完整性并输出可审计摘要。
```

### Reproduce v1-style demo flow

```
按 tutorial_v2/16-v1-demo-runbook-从零到完整展示.md 执行，
重点验证 v1 兼容路径（make pipeline-v1）及端到端结果。
```
