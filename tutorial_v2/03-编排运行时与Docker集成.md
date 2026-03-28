# 03 编排运行时与Docker集成

## 核心结论

v2 的运行时是“Dagster + 数据平台服务”的组合，真正让编排系统可用的是 Compose 里的服务依赖、环境变量注入和持久化配置。

---

## 服务拓扑（重点新增）

在 v1 的 5 服务基础上，v2 新增：

- `dagster-webserver`
- `dagster-daemon`

对应文件：

- `docker/docker-compose.yml`
- `docker/dagster/Dockerfile`

---

## `docker/dagster/Dockerfile` 你要讲清楚的点

1. 基于 `python:3.11-slim`
2. 同时安装 `requirements.txt` + `requirements-dagster.txt`
3. 拷贝 `ingestion/transformations/ml/scripts/dagster`
4. 默认启动 `dagster-webserver`

**面试点**：这是“把业务代码与编排代码打进同一执行镜像”的常见方案，减少 runtime import 失配风险。

---

## Compose 中 Dagster 两服务分工

### `dagster-webserver`

- 对外 UI（3000）
- 接收 job execute 请求
- 读取 workspace 与 definitions

### `dagster-daemon`

- schedule/sensor 的实际驱动者
- 没有 daemon，很多自动化只“可配置不可执行”

---

## 为什么要配 `DAGSTER_HOME` 与 Postgres 存储

v2 增加了 `dagster/dagster.yaml`，使用 PostgreSQL `dagster_storage` 做 instance storage。

收益：

- run/event 历史跨容器重启可保留
- 状态一致性优于本地 SQLite/临时文件

风险：

- Postgres 可用性成为编排可用性的前置条件

---

## `make` 命令层面的迁移

- `make pipeline`：默认 Dagster 路径
- `make pipeline-legacy`：旧脚本回退路径
- `make dagster-ui`：直接打开 UI

**面试表达**：命令层切换是“产品化迁移”关键，不只是代码改造。

---

## 典型故障与定位

### 问题1：`make pipeline` 执行失败，提示连不上 dagster-webserver

排查：

1. `make up`
2. `docker compose ps` 看 `dagster-webserver` 状态
3. 看 webserver 日志是否 import/依赖报错

### 问题2：schedule 配好了但不触发

排查：

1. 确认 `dagster-daemon` 运行
2. UI 确认 schedule 已启用
3. 检查时区与 cron 解释

---

## 面试 2 分钟表达模板

“v2 在运行时新增了 Dagster 的 webserver/daemon 双服务。webserver 负责 UI 与执行入口，daemon 负责 schedule/sensor 实际触发。  
同时用 PostgreSQL 作为 Dagster instance storage，保证 run/event 的持久化。  
命令层把默认入口切到 `make pipeline`，并保留 `pipeline-legacy` 作为迁移回退，这个设计重点是稳态演进而不是激进替换。”
