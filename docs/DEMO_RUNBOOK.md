# SoloLakehouse Demo 执行手册（中文，含验收清单）

本手册用于“从零到完成一次可验收 Demo”。  
目标是让第一次使用项目的人也可以**无脑执行**：照着步骤复制命令，即可完成启动、运行、验收和结论输出。

---

## 0. Demo 目标与最终交付

完成本手册后，你将交付：

1. 一套可运行的 v2.5 本地 Lakehouse 环境
2. 一次完整的 `make pipeline` 执行记录
3. 一份可勾选的验收清单（PASS/FAIL）
4. 一段最终结论（可直接放到汇报/PR/邮件）

本手册默认环境：

- OS: Linux / macOS（Windows 请使用 WSL2）
- 当前分支：建议 `main`
- 项目路径：任意（示例使用 `~/SoloLakehouse`）

**EN explanation:**  
This runbook is designed for first-time users and produces a complete, auditable demo result with a final conclusion.

---

## 1. 前置条件检查（必须先过）

### 1.1 必备工具

- `git`
- Docker + Docker Compose 插件
- Python 3.13+
- `make`

### 1.2 逐条检查命令

```bash
git --version
docker --version
docker compose version
python3 --version
make --version
```

### 1.3 成功标准

- 每条命令都返回版本号
- Docker daemon 已启动（否则后面 `make setup` 会失败）

**EN explanation:**  
If any command fails here, stop and fix tool installation first. Do not proceed.

---

## 2. 获取代码并进入项目目录

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
```

建议立刻确认路径正确：

```bash
pwd
ls
```

你应看到至少这些文件/目录：

- `Makefile`
- `docker/`
- `docs/`
- `scripts/`
- `requirements.txt`

**EN explanation:**  
All remaining commands assume you are at repository root.

---

## 3. 初始化本地 Python 运行环境

> 虽然核心服务在 Docker 里，本地仍需要 Python 环境运行 `make verify` 等脚本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

可选确认：

```bash
which python
python --version
```

成功标准：

- `which python` 指向 `.../SoloLakehouse/.venv/bin/python`
- `pip install` 无报错退出

**EN explanation:**  
Keep this venv activated in the same terminal while running demo steps.

---

## 4. 准备环境变量

```bash
cp .env.example .env
```

本地首次演示可直接使用默认 `.env`。  
如果你是旧环境（之前跑过），遇到数据库认证异常时请看“故障处理”章节。

**EN explanation:**  
For a first run, default `.env` values are expected to work.

---

## 5. 启动全栈（推荐首次用 setup）

```bash
make setup
```

该命令会自动完成：

1. Docker 可用性检查
2. `.env` 存在性检查
3. 镜像拉取
4. 全部服务启动与健康等待

首次启动可能需要数分钟（OpenMetadata/Superset/Elasticsearch 相对更慢）。

成功标准：

- 命令退出码为 0
- 无致命报错（`dependency failed to start` 之类）

**EN explanation:**  
Use `make setup` for deterministic first bootstrap. It is safer than manual piecemeal startup.

---

## 6. 健康检查（Demo 门禁）

```bash
make verify
```

成功标准：以下服务全部 `PASS`

- MinIO
- PostgreSQL
- Hive Metastore
- Trino
- MLflow
- Dagster
- OpenMetadata
- Superset

若个别服务刚启动还未就绪，等待 10-30 秒后重跑一次 `make verify`。

**EN explanation:**  
Do not continue to pipeline execution until all services pass health checks.

---

## 7. 执行主流程 Demo（数据管道）

```bash
make pipeline
```

该命令通过 Dagster 执行 `full_pipeline_job`，是 v2.5 主线唯一支持入口。

成功标准：

- 命令退出码为 0
- 终端无未处理异常

建议补做一次健康复核：

```bash
make verify
```

**EN explanation:**  
This is the core business demo action: one full end-to-end pipeline run.

---

## 8. UI 验收（可视化确认）

打开以下页面并逐项检查：

| 服务 | URL | 期望 |
|------|-----|------|
| MinIO Console | `http://localhost:9001` | 页面可访问，桶存在（`sololakehouse`、`mlflow-artifacts`） |
| Trino UI | `http://localhost:8080` | 页面可访问，服务状态正常 |
| MLflow UI | `http://localhost:5000` | 页面可访问，无 Host header 报错 |
| Dagster UI | `http://localhost:3000` | 可看到最近一次 pipeline run |
| OpenMetadata | `http://localhost:8585` | 页面可访问 |
| Superset | `http://localhost:8088` | 可登录（默认 `admin / admin`） |

**EN explanation:**  
These UI checks validate both service readiness and demo visibility for stakeholders.

---

## 9. 数据与结果验收（强烈建议）

### 9.1 使用 Trino 验证 Gold 数据可查询

方式 A（UI）：在 Trino UI 中执行 SQL。  
方式 B（命令行）：在 Trino 容器执行。

示例 SQL（至少执行一条）：

```sql
SELECT count(*) AS total_rows
FROM hive.gold.ecb_dax_features;
```

```sql
SELECT count(*) AS total_rows
FROM iceberg.gold.ecb_dax_features_iceberg;
```

成功标准：

- SQL 执行成功
- 结果行数 > 0

### 9.2 使用 MLflow 验证实验记录

在 MLflow UI 中确认：

- 至少存在一次 run
- 该 run 有时间戳、状态、关键指标（如有）

### 9.3 使用 Dagster 验证编排成功

在 Dagster UI 中确认：

- 最近一次 `full_pipeline_job` 为成功状态（success）
- 关键节点未出现失败重试风暴

**EN explanation:**  
This section proves that the demo is not only “services up” but also “business pipeline produced outputs”.

---

## 10. Demo 验收清单（复制即可用）

> 建议演示者一边执行一边勾选。  
> 全部 `PASS` 才可判定 Demo 完成。

- [ ] 环境工具检查通过（git/docker/python/make）
- [ ] 代码成功 clone 并进入仓库根目录
- [ ] `.venv` 创建成功且依赖安装完成
- [ ] `.env` 已创建
- [ ] `make setup` 成功
- [ ] `make verify` 首次全 PASS
- [ ] `make pipeline` 成功执行
- [ ] `make verify` 二次复核 PASS
- [ ] MinIO UI 可访问且桶存在
- [ ] Trino UI 可访问
- [ ] MLflow UI 可访问且无 Host header 错误
- [ ] Dagster UI 可看到成功 run
- [ ] OpenMetadata UI 可访问
- [ ] Superset UI 可登录
- [ ] Trino 查询 `hive.gold.ecb_dax_features` 成功且有数据
- [ ] Trino 查询 `iceberg.gold.ecb_dax_features_iceberg` 成功且有数据
- [ ] MLflow 中可见 run 记录

**结论规则：**

- 勾选项全部通过 => Demo 结论为 **PASS**
- 存在任一关键项失败（pipeline / verify / Gold 查询）=> Demo 结论为 **FAIL**

**EN explanation:**  
Use this checklist as the formal acceptance gate for demo sign-off.

---

## 11. 最终结论模板（可直接复制）

### 11.1 中文结论模板

```text
【SoloLakehouse v2.5 Demo 结论】
执行时间：<YYYY-MM-DD HH:MM>
执行人：<name>
环境：<OS + Docker + Python version>

结果：PASS / FAIL

验收摘要：
- 服务健康检查：<PASS/FAIL>
- Pipeline 执行：<PASS/FAIL>
- Gold 数据查询：<PASS/FAIL>
- MLflow 运行记录：<PASS/FAIL>
- UI 可访问性（6项）：<PASS/FAIL>

备注：
<若失败，写明失败步骤、错误信息、下一步修复计划>
```

### 11.2 English conclusion template

```text
[SoloLakehouse v2.5 Demo Conclusion]
Execution time: <YYYY-MM-DD HH:MM>
Executed by: <name>
Environment: <OS + Docker + Python version>

Result: PASS / FAIL

Acceptance summary:
- Service health checks: <PASS/FAIL>
- Pipeline execution: <PASS/FAIL>
- Gold data query checks: <PASS/FAIL>
- MLflow run visibility: <PASS/FAIL>
- UI accessibility (6 items): <PASS/FAIL>

Notes:
<If failed, include failed step, error, and mitigation plan>
```

---

## 12. 常见故障快速修复（演示现场版）

### 12.1 Hive Metastore 连接 PostgreSQL 失败

症状：

- `hive-metastore` 日志出现 `password authentication failed for user "postgres"`

修复：

```bash
docker exec slh-postgres psql -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
make up
make verify
```

### 12.2 MLflow 报 `Invalid Host header`

症状：

- 打开 `http://localhost:5000` 报 DNS rebinding 拦截

修复：

```bash
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.openmetadata.yml -f docker/docker-compose.superset.yml up -d --build mlflow
make verify
```

### 12.3 `make up` 或 `make setup` 首次较慢

说明：

- OpenMetadata / Elasticsearch / Superset 首次启动时间较长

建议：

```bash
make verify
```

等待后重试，直到全 PASS。

**EN explanation:**  
These are the three most common blockers during live demos. Keep these commands ready.

---

## 13. 演示结束后的收尾

### 保留数据（推荐）

```bash
make down
```

### 清空环境（危险）

```bash
make clean
docker image prune -f
docker volume prune -f
```

---

## 14. 一键“抄作业”最短路径

如果你只想最快跑完一次 demo，按顺序执行：

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make setup
make verify
make pipeline
make verify
```

跑完后按第 10 节清单打勾，并输出第 11 节结论即可。
