# Agent Prompt Reference

Prompts for AI coding agents working on the current v2.5 single-track codebase.

## Baseline prompt

```
读取 CLAUDE.md、docs/roadmap.md、docs/history/timeline.md，
确认当前基线是 v2.5 单轨运行（Dagster + OpenMetadata + Superset 必选），
然后执行任务并汇报变更文件与验证结果。
```

## Verification prompt

```
依次运行 make verify、make pipeline、make test、make lint、make typecheck，
定位失败项并修复，输出根因与修复说明。
```

## Docs consistency prompt

```
扫描 README.md 与 docs/，
确保不再出现已移除命令或入口（如 pipeline-v1、pipeline-legacy、PIPELINE_MODE），
将历史叙述保留在 docs/history/ 下。
```

## Runtime troubleshooting prompt

```
运行 make verify，
若失败，按服务优先级定位（PostgreSQL/Trino/MLflow/Dagster/OpenMetadata/Superset），
给出可执行修复步骤并复验。
```
