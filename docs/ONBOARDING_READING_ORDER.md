# 新接手者文档阅读顺序

本文帮助**刚接手 SoloLakehouse**的同学在文档很多的情况下，用最小路径建立全局认知，再按需深入。阅读时间可按阶段切分；同一主题的中英文件选一种即可，避免重复劳动。

**速记锚点**

- **当前运行时基线**：v2.5（单轨 Docker Compose + Dagster + Trino Iceberg Gold + OpenMetadata + Superset）。权威说明见 `docs/roadmap.md`。
- **日常执行 backlog**：仓库根目录 `TASKS.md`。
- **文档总索引**：`docs/README.md`。
- **给 AI/Agent 的仓库速查**（人类也可扫一眼命令与目录）：`CLAUDE.md`。

---

## 阶段 0：10 分钟建立坐标（必读）

按顺序读，知道「这是什么、能跑什么、边界在哪」。

| 顺序 | 文档 | 目的 |
|------|------|------|
| 1 | [README.md](../README.md) | 项目定位、一句话架构、Quick Start 入口。 |
| 2 | [docs/README.md](README.md) | 全站文档地图，之后迷路先回到这里。 |
| 3 | [docs/roadmap.md](roadmap.md) | 版本状态（v2.5 当前 / v3 方向）与路线图。 |
| 4 | [docs/ASSESSMENT_LAKEHOUSE_DAX_ECB.md](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) | 自评：参考实现的诚实边界，避免过度承诺。 |

---

## 阶段 1：把环境跑起来并验收（动手优先）

在阶段 0 之后立刻动手，比继续读长文更有效。

| 顺序 | 文档 | 目的 |
|------|------|------|
| 5 | [docs/quickstart.md](quickstart.md) | 最短路径：clone → setup → verify → demo。 |
| 6 | [docs/DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) 或 [docs/DEMO_RUNBOOK_EN.md](DEMO_RUNBOOK_EN.md) | 完整 Demo / 验收清单与结论模板（中英二选一）；`make demo` 是验收入口，`make pipeline` 是含 MLflow 的完整流水线。 |
| 7 | [docs/deployment.md](deployment.md) | 前置条件、部署、运维与排障（跑不通时回到这篇）。 |

---

## 阶段 2：日常怎么用平台（Operator / 数据消费者）

| 顺序 | 文档 | 目的 |
|------|------|------|
| 8 | [docs/DAGSTER_GUIDE.md](DAGSTER_GUIDE.md) | Dagster 作业、调度、UI 与运行期习惯。 |
| 9 | [docs/USER_GUIDE.md](USER_GUIDE.md) 或 [docs/USER_GUIDE_EN.md](USER_GUIDE_EN.md) | 面向使用者的完整说明（中英二选一）。 |

---

## 阶段 3：架构与数据契约（改代码前必读）

| 顺序 | 文档 | 目的 |
|------|------|------|
| 10 | [docs/architecture.md](architecture.md) | 分层与组件关系。 |
| 11 | [docs/medallion-model.md](medallion-model.md) | Bronze / Silver / Gold 约定与数据契约。 |
| 12 | [docs/decisions/README.md](decisions/README.md) | ADR 索引；先扫目录，再按需打开单篇。 |

**ADR 建议优先级（在读完 ADR 索引后）**

- **理解当前栈为何长这样**：ADR-001～005（v1 基础取舍）、ADR-006（Dagster 编排）、ADR-013（Iceberg Gold）、ADR-014（OpenMetadata 相关历史说明，与当前默认栈对照阅读）。
- **规划与争议中的方向**：ADR-016（计算引擎迁移提案）、ADR-007～012（v3 基础设施与治理）、ADR-015～018（可观测性、目录与血缘等演进占位）。
- **v2.5 freeze 取舍**：ADR-019（SeaweedFS 延后记录）。

不必第一天读完所有 ADR；遇到具体决策点再读对应编号即可。

---

## 阶段 4：版本史、规划与「接下来做什么」

需要回答「为什么现在是这个形态」「下一版要做什么」时读。

| 顺序 | 文档 | 目的 |
|------|------|------|
| 13 | [TASKS.md](../TASKS.md) | 当前仓库执行任务板（与 roadmap 配套）。 |
| 14 | [docs/history/README.md](history/README.md) | 历史文档导航。 |
| 15 | [docs/history/timeline.md](history/timeline.md) | 按版本的时间线。 |
| 16 | [docs/history/architecture-evolution.md](history/architecture-evolution.md) | 架构随时间的演变与取舍摘要。 |
| 17 | [docs/history/v3-planning.md](history/v3-planning.md) | v3 生产化与治理方向的规划草案（主规划入口）。 |

**可选（更细的版本规划笔记，按需）**

- `docs/history/v2-planning.md`、`v2.5-planning.md`、`v2.6-planning.md`～`v2.9-planning.md`：各阶段交付与迁移上下文；排查「当时为什么这样改」时查阅。

---

## 阶段 5：v3 治理与发布纪律（准备上生产或参与治理时）

| 顺序 | 文档 | 目的 |
|------|------|------|
| 18 | [docs/v3-governance-navigation.md](v3-governance-navigation.md) | v3 治理主题导航。 |
| 19 | [docs/governance-v3-matrix.md](governance-v3-matrix.md) | 治理矩阵类总览（若存在且与当前工作相关）。 |
| 20 | [docs/governance-v3-runbook.md](governance-v3-runbook.md) | 治理相关运行手册。 |
| 21 | [docs/v3-spec.md](v3-spec.md) | v3 规格/要求类说明（与规划、ADRs 交叉验证）。 |
| 22 | [docs/V3_RELEASE_CHECKLIST.md](V3_RELEASE_CHECKLIST.md) | v3 发布级检查清单。 |

同时回顾阶段 3 中的 v3 相关 ADR（007～012、015 等）。

---

## 阶段 6：协作、发布与质量（参与贡献或发版时）

| 顺序 | 文档 | 目的 |
|------|------|------|
| 23 | [docs/contributing.md](contributing.md) | 贡献约定。 |
| 24 | [docs/git-workflow.md](git-workflow.md) | 分支与协作流程。 |
| 25 | [docs/release.md](release.md) | 发布Runbook。 |
| 26 | [docs/release-readiness.md](release-readiness.md) | 发布前自检。 |
| 27 | [docs/V1_RELEASE_CHECKLIST.md](V1_RELEASE_CHECKLIST.md)、[docs/V2_RELEASE_CHECKLIST.md](V2_RELEASE_CHECKLIST.md) | 历史版本检查清单（审计或对照过时栈时）。 |

---

## 可选：中文规划快照与英文对照（避免重复读）

以下成对文件主题相近，**读一种语言即可**。

| 中文 | 英文（或对应） |
|------|----------------|
| [docs/企业级演进规划_2026-05-05.md](企业级演进规划_2026-05-05.md) | [docs/enterprise-evolution-plan-2026-05-05.md](enterprise-evolution-plan-2026-05-05.md) |
| [docs/项目现状总览_2026-05-05.md](项目现状总览_2026-05-05.md) | [docs/project-state-overview-2026-05-05.md](project-state-overview-2026-05-05.md) |

历史某一时间点的快照（若需要对比「当时写了什么」）：

- [docs/项目快照_2026-03-26.md](项目快照_2026-03-26.md)

---

## 仅在与 AI 协作或写自动化时需要

- [docs/agent-prompts.md](agent-prompts.md)：与 Agent 配合时的提示与工作流片段。

---

## 建议周报式节奏（可复制）

| 天数 | 目标 |
|------|------|
| 第 1 天 | 阶段 0～1：坐标 + 本地跑通 + Demo Runbook 走一遍。 |
| 第 2～3 天 | 阶段 2～3：用户指南 + 架构/Medallion + ADR 索引与核心几篇。 |
| 第 4 天起 | 按角色深入：开发侧重 `TASKS.md` 与代码；平台/治理侧重阶段 5；发版侧重阶段 6。 |

读完阶段 0～3 后，你已具备「能运行、能排障、能解释架构」的起点；其余文档作为**按需查阅**的辞典即可。
