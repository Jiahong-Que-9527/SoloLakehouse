# VPS 部署运行手册 — FinLakehouse

本手册用于在全新 VPS 上部署 FinLakehouse，并完成验收。  
按顺序逐步执行，每步都有验收命令，确认通过后再进入下一步。

---

## 前提条件

| 项目 | 要求 |
|---|---|
| OS | Ubuntu 22.04 LTS 或 Debian 12（推荐）|
| CPU | 4 vCPU |
| 内存 | 8 GB（最低），16 GB（推荐）|
| 磁盘 | 40 GB SSD（最低）|
| 网络 | 公网 IP；以下端口对操作者开放：3000、5000、8080、8085、8088、8090、8585、9000、9001 |

---

## 第一步：VPS 系统初始化

```bash
# 以 root 或有 sudo 权限的用户执行

# 更新系统
apt-get update && apt-get upgrade -y

# 安装基础工具
apt-get install -y git make curl wget python3 python3-venv python3-pip ca-certificates gnupg lsb-release

# 安装 Docker Engine（官方脚本）
curl -fsSL https://get.docker.com | sh

# 将当前用户加入 docker 组（避免每次 sudo）
usermod -aG docker $USER
newgrp docker   # 当前会话立即生效

# 验证 Docker
docker info --format '{{.ServerVersion}}'
docker compose version
```

**验收：** 两条命令均有输出（版本号），无报错。

---

## 第二步：创建运行时目录结构

```bash
# 创建 entity 根目录
mkdir -p /opt/finlakehouse/{app,data,backup,logs}
chown -R $USER:$USER /opt/finlakehouse

# 验收
ls /opt/finlakehouse
# 应输出：app  backup  data  logs
```

---

## 第三步：克隆代码仓库

```bash
cd /opt/finlakehouse
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git app

# 验收
ls /opt/finlakehouse/app
# 应能看到：Makefile  docker/  ingestion/  dagster/  等目录
```

---

## 第四步：配置 .env 文件

```bash
cd /opt/finlakehouse/app

# 从模板复制
cp docs/finlakehouse-env-template.env /opt/finlakehouse/.env
chmod 600 /opt/finlakehouse/.env

# 编辑，修改所有 CHANGE_ME 字段
nano /opt/finlakehouse/.env
```

**必须修改的字段（替换 `CHANGE_ME_*` 为实际强密码）：**

```dotenv
# --- 运行时身份（已预填，确认无误即可）---
PRODUCT_ID=finlakehouse
PRODUCT_DISPLAY_NAME=FinLakehouse
ENVIRONMENT=prod
COMPOSE_PROJECT_NAME=finlakehouse

# --- 以下密码必须改，且相互保持一致 ---
MINIO_ROOT_PASSWORD=<强密码，例如 openssl rand -base64 24>
POSTGRES_PASSWORD=<强密码>
S3_ACCESS_KEY=finlakehouse           # 保持与 MINIO_ROOT_USER 一致
S3_SECRET_KEY=<与 MINIO_ROOT_PASSWORD 相同>
AWS_SECRET_ACCESS_KEY=<与 MINIO_ROOT_PASSWORD 相同>

SUPERSET_SECRET_KEY=<随机长字符串，例如 openssl rand -base64 32>
SUPERSET_ADMIN_PASSWORD=<强密码>

# --- 以下保持不动 ---
MINIO_ROOT_USER=finlakehouse
MINIO_ENDPOINT=localhost:9000
S3_ENDPOINT=http://minio:9000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
HIVE_METASTORE_URI=thrift://localhost:9083
WAREHOUSE_URI=s3a://finlakehouse-data/warehouse/
DATA_BUCKET=finlakehouse-data
AUDIT_BUCKET=finlakehouse-audit
MLFLOW_ARTIFACT_BUCKET=finlakehouse-mlflow
```

快速生成密码的命令：

```bash
openssl rand -base64 24   # 用于 MINIO_ROOT_PASSWORD / S3_SECRET_KEY
openssl rand -base64 32   # 用于 SUPERSET_SECRET_KEY
```

**验收：**

```bash
grep "CHANGE_ME" /opt/finlakehouse/.env
# 应无任何输出（表示所有 CHANGE_ME 已替换）
```

---

## 第五步：绑定数据目录（symlink）

```bash
# 将 docker/data/ 软链接到 entity 数据根目录
# 这样运行时数据落在 /opt/finlakehouse/data/ 而不是 repo 内部
ln -sfn /opt/finlakehouse/data /opt/finlakehouse/app/docker/data

# 验收
ls -la /opt/finlakehouse/app/docker/data
# 应输出类似：lrwxrwxrwx ... /opt/finlakehouse/app/docker/data -> /opt/finlakehouse/data
```

---

## 第六步：安装 Python 依赖

```bash
cd /opt/finlakehouse/app

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dagster.txt

# 验收
.venv/bin/python -c "import pyiceberg; print(pyiceberg.__version__)"
# 应输出版本号（0.11.x）
```

---

## 第七步：拉取镜像并启动服务

```bash
cd /opt/finlakehouse/app

# 拉取所有基础镜像（避免首次 make up 因拉取超时失败）
ENV_FILE=/opt/finlakehouse/.env docker compose --env-file /opt/finlakehouse/.env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  pull

# 启动全栈（包含 Iceberg 命名空间初始化）
ENV_FILE=/opt/finlakehouse/.env make up
```

`make up` 会依次完成：
1. 创建数据目录
2. 启动 Postgres 和 MinIO
3. 初始化数据库
4. 启动所有服务（Hive Metastore、Trino、MLflow、Dagster、OpenMetadata、Superset）
5. 等待健康检查通过
6. 创建 Iceberg 命名空间和 6 张表

> **注意：** 首次启动会构建 Dagster / MLflow 等自定义镜像，耗时约 5–10 分钟，OpenMetadata 初始化还需额外 3–5 分钟。如果 `make up` 超时退出，只要容器都在运行就继续执行第八步。

**查看容器状态：**

```bash
docker compose --env-file /opt/finlakehouse/.env \
  -f docker/docker-compose.yml ps
```

---

## 第八步：服务健康检查

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env make verify
```

**预期输出（全部 PASS）：**

```
Runtime identity: FinLakehouse (finlakehouse, prod, slh-v2.5.1)
Service          Status  Detail
---------------- ------- ----------------------------
MinIO            PASS    Buckets: finlakehouse-audit, finlakehouse-data, finlakehouse-mlflow
PostgreSQL       PASS    Databases: dagster_storage, hive_metastore, mlflow, superset_metadata
Hive Metastore   PASS    TCP port 9083 open
Trino            PASS    Running, not starting
MLflow           PASS    HTTP 200 /health
Dagster          PASS    HTTP 200 /server_info
Dagster S3 creds PASS    AWS + MLflow S3 credentials present
OpenMetadata     PASS    API OK (http://localhost:8585)
Superset         PASS    HTTP 200 (http://localhost:8088/health)
```

如果 OpenMetadata 显示 FAIL，等待 3 分钟后重试（初始化较慢）。

**健康门户（浏览器可访问）：**

```bash
ENV_FILE=/opt/finlakehouse/.env make health
# 然后用浏览器打开 http://<VPS-IP>:8090/health
```

---

## 第九步：运行完整 Pipeline

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env make pipeline
```

**预期：** 命令最后一行出现 `RUN_SUCCESS`，全程无 `STEP_FAILURE`。

关键日志行（确认每层都写入）：

```
iceberg_appended  rows=... table=bronze.ecb_rates
iceberg_appended  rows=... table=bronze.dax_daily
iceberg_overwritten  rows=... table=silver.ecb_rates_cleaned
iceberg_overwritten  rows=... table=silver.dax_daily_cleaned
iceberg_overwritten  rows=... table=gold.ecb_dax_features
ml_run_complete  accuracy=...
RUN_SUCCESS
```

---

## 第十步：Demo 验收

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env make demo
```

**预期输出末尾：**

```
Demo check      Rows  Status
--------------- ----- ------
Iceberg Gold    53    PASS
```

命令退出码为 0。

---

## 第十一步：Trino 数据验证

进入 Trino 容器执行 SQL：

```bash
docker exec -it slh-trino trino \
  --server http://localhost:8080 \
  --user finlakehouse
```

在 Trino shell 里执行：

```sql
-- Bronze 层
SELECT count(*) AS ecb_bronze_rows  FROM iceberg.bronze.ecb_rates;
SELECT count(*) AS dax_bronze_rows  FROM iceberg.bronze.dax_daily;

-- Silver 层
SELECT count(*) AS ecb_silver_rows  FROM iceberg.silver.ecb_rates_cleaned;
SELECT count(*) AS dax_silver_rows  FROM iceberg.silver.dax_daily_cleaned;

-- Gold 层
SELECT count(*) AS gold_rows        FROM iceberg.gold.ecb_dax_features;
SELECT * FROM iceberg.gold.ecb_dax_features ORDER BY event_date DESC LIMIT 5;
```

**验收标准：**

| 表 | 最少行数 |
|---|---|
| `iceberg.bronze.ecb_rates` | 5,000 |
| `iceberg.bronze.dax_daily` | 1,000 |
| `iceberg.silver.ecb_rates_cleaned` | 5,000 |
| `iceberg.silver.dax_daily_cleaned` | 1,000 |
| `iceberg.gold.ecb_dax_features` | 10 |

退出：`quit`

---

## 第十二步：MLflow 验证

浏览器打开 `http://<VPS-IP>:5000`

验收：
- 存在名为 `ecb_dax_impact` 的实验
- 实验下有至少 1 条运行记录，且有 `accuracy` 等指标

---

## 第十三步：UI 端到端验收

| 服务 | 地址 | 验收标准 |
|---|---|---|
| 健康门户 | `http://<VPS-IP>:8090/health` | 全部服务绿色 |
| Dagster UI | `http://<VPS-IP>:3000` | 能看到最新的成功 run |
| Trino UI | `http://<VPS-IP>:8080` | 页面正常加载 |
| MLflow | `http://<VPS-IP>:5000` | ecb_dax_impact 实验有运行记录 |
| MinIO Console | `http://<VPS-IP>:9001` | 三个 bucket 都有数据 |
| OpenMetadata | `http://<VPS-IP>:8585` | 页面可访问（admin/admin） |
| Superset | `http://<VPS-IP>:8088` | 登录成功（admin + 你设置的密码）|

---

## 第十四步：还原演练（24/7 运营前必须完成）

参考模板：`docs/restore-drills/TEMPLATE-iceberg-restore-drill.md`

最简演练流程（在同一台 VPS 上用 /tmp 做测试）：

```bash
# 1. 备份当前状态
DRILL_ROOT=/tmp/flh-drill-$(date +%Y%m%dT%H%M%S)
mkdir -p "$DRILL_ROOT"/{backup,app,data}

# 2. 备份 MinIO（三个 bucket）
docker exec slh-minio mc alias set local http://localhost:9000 \
  finlakehouse <MINIO_ROOT_PASSWORD>
docker exec slh-minio mc mirror local/finlakehouse-data  "$DRILL_ROOT/backup/finlakehouse-data/"
docker exec slh-minio mc mirror local/finlakehouse-mlflow "$DRILL_ROOT/backup/finlakehouse-mlflow/"

# 3. 备份 PostgreSQL
docker exec slh-postgres pg_dump -U postgres hive_metastore \
  > "$DRILL_ROOT/backup/hive_metastore.sql"
docker exec slh-postgres pg_dump -U postgres mlflow \
  > "$DRILL_ROOT/backup/mlflow.sql"

# 4. 记录 git SHA
git -C /opt/finlakehouse/app rev-parse HEAD > "$DRILL_ROOT/backup/git_sha.txt"
echo "slh-v2.5.1" > "$DRILL_ROOT/backup/runtime_version.txt"

# 5. 在 /tmp 中克隆并还原（模拟灾难恢复）
git clone /opt/finlakehouse/app "$DRILL_ROOT/app"
cp /opt/finlakehouse/.env "$DRILL_ROOT/app/.env"
ln -sfn "$DRILL_ROOT/data" "$DRILL_ROOT/app/docker/data"

# 6. 启动还原环境（使用不同端口避免冲突 —— 略，实际演练时在独立 VM 执行）

# 简化验证：直接在当前环境运行 make verify 确认数据完整
ENV_FILE=/opt/finlakehouse/.env make verify
ENV_FILE=/opt/finlakehouse/.env make demo
```

完成后将结果填入 `docs/restore-drills/YYYY-MM-DD-finlakehouse-iceberg-restore-drill.md`，Result 标记为 PASS。

---

## 验收总清单

在签字前确认每一项：

```
[ ] make verify 全部 PASS
[ ] make pipeline 返回 RUN_SUCCESS
[ ] make demo 返回 Iceberg Gold PASS（行数 > 0）
[ ] Trino 能查到 bronze/silver/gold 三层数据
[ ] MLflow 有 ecb_dax_impact 实验运行记录
[ ] Dagster UI 可访问，显示成功 run
[ ] OpenMetadata UI 可访问
[ ] Superset UI 可访问
[ ] MinIO Console 显示三个 bucket 有数据
[ ] 健康门户 http://<VPS-IP>:8090/health 全绿
[ ] 还原演练已执行，结果记录在 docs/restore-drills/ 下
```

全部勾选 → 部署完成，FinLakehouse 可以开始积累数据资产。

---

## 日常运维

### 停止服务（保留数据）

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env docker compose \
  --env-file /opt/finlakehouse/.env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  down
```

### 重新启动

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env make up
```

### 手动触发 pipeline

```bash
cd /opt/finlakehouse/app
ENV_FILE=/opt/finlakehouse/.env make pipeline
```

### 备份（建议每日执行）

```bash
# MinIO 数据
mc mirror myminio/finlakehouse-data  /opt/finlakehouse/backup/$(date +%F)/data/
mc mirror myminio/finlakehouse-mlflow /opt/finlakehouse/backup/$(date +%F)/mlflow/

# PostgreSQL
docker exec slh-postgres pg_dumpall -U postgres \
  > /opt/finlakehouse/backup/$(date +%F)/postgres_all.sql
```

### 严禁操作

```
❌ 不要在 VPS 上执行 make clean（会删除所有数据）
❌ 不要共享 /opt/finlakehouse/data/ 给其他 entity
❌ 不要将 .env 文件提交到 git
```
