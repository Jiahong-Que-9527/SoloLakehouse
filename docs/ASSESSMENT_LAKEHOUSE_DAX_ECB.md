# SoloLakehouse 评估报告：作为 Lakehouse 项目的合理性与 DAX/ECB 端到端可跑通性

> 评估目标：判断 SoloLakehouse 是否是一个"合理的 Lakehouse 参考实现"，并评估基于 ECB（欧央行主要再融资利率）+ DAX（德国股指）两个数据源能否**完整跑通** Bronze → Silver → Gold → ML 全链路；对不完整/不规范的地方给出补充建议。
>
> 评估日期：2026-04-17
> 评估基线：`main` 分支（v2.5 single-track runtime）
> 评估范围：架构合理性 / 端到端可执行性 / 数据与建模合理性 / 可运维性

---

## 1. 结论（TL;DR）

| 维度 | 结论 | 说明 |
|------|------|------|
| 是否是一个"合理的 Lakehouse 项目" | **是**（参考实现级别，非生产级） | 具备 Lakehouse 的所有标志性层次：对象存储 / 开放表格式 / 统一元数据 / 分离计算 / 编排 / ML / 目录 / BI。 |
| 用 ECB+DAX 是否能**一次性跑通端到端** | **能跑通，但"完整"要打折扣** | `make up` + `make pipeline` 可以走通 `bronze → silver → gold(Iceberg) → MLflow`；但 DAX 数据只到 2024-12-31 且来源是本地静态 CSV，不是实时/增量接入，并且该 CSV 的数值与真实 DAX 指数存在明显偏差。 |
| 是否是"生产就绪的 Lakehouse" | **不是** | v2.5 明确是参考/演示基线，生产就绪目标放在 v3.0（K8s/Helm/Terraform + 环境晋升 + 秘钥治理 + SLO），目前属于"功能齐 + 工程规范齐，但运行保证不足"。 |

一句话定位：**它是一个工程规范写得相当好的单机 Lakehouse 参考实现，教学/演示用合格；但"真正的端到端可信运行"需要把 DAX 数据源、Iceberg Gold 写法、数据契约/质量门、Silver 分区以及运维观测补齐**。

---

## 2. 架构合理性评估

### 2.1 Lakehouse 的核心要素是否齐备？

Lakehouse 的关键标志是：**开放表格式 + 对象存储 + 分离计算 + 统一元数据 + 医patientine 分层**。本项目对照如下：

| Lakehouse 要素 | 本项目实现 | 合理性 |
|--------------|-----------|--------|
| 对象存储 | MinIO（S3 兼容） | 合理，开源 S3 语义 |
| 开放表格式（Gold） | Apache Iceberg（通过 Trino 写入） | 合理，Gold 是主要查询/治理对象 |
| Bronze/Silver 存储格式 | Parquet（snappy） | 合理，对参考实现够用 |
| 统一元数据 | Apache Hive Metastore（Hive + Iceberg 共用） | 合理，对单节点足够 |
| 分离计算 | Trino 查询 + Python pandas 转换（Dagster 编排） | 合理，但 Silver 转换走本地 pandas 而非 Trino，是参考实现取舍 |
| 医patientine 分层 | Bronze/Silver/Gold 明确分离，各有独立 prefix | 合理 |
| 编排 | Dagster（asset-aware，含 schedule / sensor / asset check） | **较好**，asset + check + sensor + schedule 齐全 |
| ML 追踪 | MLflow（Postgres + MinIO artifact store） | 合理 |
| 数据目录 | OpenMetadata | 合理 |
| BI/查询 UI | Superset（基于 Trino） | 合理 |
| 验证层 | Pydantic v2 + 自定义 bronze quality checks | 合理，"fail-fast" 明确 |

> 结论：**架构形态是合理的 Lakehouse 参考实现**，五层模型（Sources → Ingestion → Medallion → Query → ML）+ 三层平台服务（Orchestration / Catalog / BI）齐备，Iceberg 放在 Gold、Parquet 放在 Bronze/Silver 是一个务实取舍，并在 `ADR-003` / `ADR-013` 中有明确记录。

### 2.2 哪些地方"像 Lakehouse 但并未完全兑现"

这些是**概念到位、实现简化**的地方——不致命，但影响"成熟度"判断：

1. **Bronze 是真 partition，Silver/Gold 不是。**
   - Bronze 按 `ingestion_date=YYYY-MM-DD` 分区写入，immutable（符合医patientine 规范）。
   - Silver 每次覆写到固定路径 `silver/<dataset>_cleaned/<dataset>_cleaned.parquet`，没有历史版本。
   - Gold（Parquet 落地层）同样是固定文件覆写。
   - Iceberg Gold 用 `DROP TABLE IF EXISTS + CTAS`，**每次重建、快照历史被丢弃**。
   - 结果：**Iceberg 选型没有兑现其最核心价值（快照 / time travel / schema evolution）**。

2. **Silver 转换发生在 pandas 进程内，而不是 Trino SQL。**
   - 对参考实现合理，但当数据量增长时它是瓶颈。
   - 教学上需要让读者明白："这里是刻意简化"而不是"Lakehouse 就这样"。

3. **`rate_change_bps` 在 Silver 层全历史计算，没有 watermark / 幂等契约。**
   - 每次 Silver 运行都会把完整 Bronze 合并后从头计算，重复但结果幂等，暂时能接受；量级上去会变成问题。

### 2.3 工程规范面

这块做得明显比一般"个人 demo"好：

- ADR（001–014）完整、决策有记录
- 代码结构清晰、`CLAUDE.md`（Agent Guide）可读性高
- 测试分 `tests/`（mock，无 Docker）+ `tests/integration/`
- `ruff` + `mypy` CI 配置齐
- `requirements.txt` 与 `requirements-dagster.txt` 分离
- `scripts/verify-setup.py` 做健康检查
- 有 Dagster schedule、sensor、asset check
- 有医patientine 文档、roadmap、release checklist

这些是"项目合理性"的重要加分项。

---

## 3. "用 DAX+ECB 跑通端到端"的评估

### 3.1 当前已经能跑通的部分

以默认 `make up` + `make pipeline` 为路径，下列链路是**实际可运行**的：

1. `ecb_bronze`：`ECBCollector` 从 `https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.MRR_RT.LEV` 拉取 MRO 利率，校验 → 写 `bronze/ecb_rates/ingestion_date=<today>/`。
2. `dax_bronze`：`DAXCollector` 读取 `data/sample/dax_daily_sample.csv`（6522 行，2000-01-03 到 2024-12-31），校验 → 写 `bronze/dax_daily/ingestion_date=<today>/`。
3. `ecb_silver` / `dax_silver`：合并所有 Bronze 分区 → 类型转换 / 前向填充 / 周末过滤 / 衍生字段 → 固定 Silver Parquet。
4. `gold_features`：以 ECB 变动事件为锚点做 event-study 特征（pre 5 天 volatility，post 5 天累计收益等），落地 Parquet，并通过 Trino 建 Hive 外表 + CTAS 生成 Iceberg Gold 表。
5. `ml_experiment`：从 **Trino 的 Iceberg Gold** 或（无 Trino 时）MinIO Parquet 读入 Gold → XGBoost+LightGBM × 3×2 网格 × TimeSeriesSplit(5) CV → 全部记录到 MLflow，返回最优 `run_id`。
6. `gold_features_min_rows_check`：断言 Gold 至少有 10 行。

只要 Docker 服务齐备、ECB API 可访问、没有日内重复运行被跳过，这条链路确实能**一次性**跑出一个最优模型 run。

### 3.2 存在的"端到端打折"问题

以下问题不会让流水线报错，但会让"端到端跑通"这件事的说服力打折：

#### (P1) DAX 不是真实时数据源，只是一份静态 CSV

- `DAXCollector._fetch_data` 直接 `pd.read_csv("data/sample/dax_daily_sample.csv")`。
- 该 CSV 只到 **2024-12-31**；ECB 实际在 2025 年之后仍然有利率变动事件，但由于 DAX 数据停摆，**所有 2025 年之后的 ECB 事件在 `build_gold_features` 里都会因为 `post_window` 不满 5 行被丢弃**。
- CSV 数值与真实 DAX 历史走势也不一致（2024-12-31 收盘 `10128.23`，真实 DAX 当年收盘在 19000+ 区间），这是**测试用合成序列**但未在文档中标注。
- 结果：表面是"双数据源"，实际 DAX 是"伪数据"，`ADR-004` 里的"公开真实数据"叙事与代码现状不完全一致。

#### (P2) Iceberg Gold 没有兑现 Iceberg 的核心价值

- `refresh_iceberg_gold_from_hive` = `DROP TABLE IF EXISTS` + `CREATE TABLE AS SELECT * FROM hive.gold.ecb_dax_features`。
- 等价于"每跑一次全量覆写"，失去快照、time travel、审计价值。
- 对于一个**以 Iceberg 为卖点**的 Gold 层，这是个明显 regression。

#### (P3) 运行幂等的边界有点脆弱

- `DAXCollector._already_ingested_today()` 如果当天同分区已有文件就 `skip`，这对 CSV 重放是合理的；但它只依赖 prefix 下有没有 `ingestion_date=today`，**没有对 CSV 内容做版本指纹**——如果你替换了 `data/sample/dax_daily_sample.csv` 但当天已经写过一次，系统会悄悄 skip，新数据不会进入 Bronze。
- ECB 侧同理。

#### (P4) Asset check 密度不足

- 当前只有一个 `gold_features` 行数 ≥ 10 的 check。
- 没有 freshness check（Gold 的 `event_date` 最大值是否接近 today 的滑窗）。
- 没有 schema/null-rate check。
- 这与 `TASKS.md` 的 A2/A1 块（"quality gate tightening"、"dataset governance baseline"）所要求的缺口吻合。

#### (P5) Bronze 和 Silver 的"真实增量语义"没闭环

- Bronze 按日期分区 immutable，OK。
- Silver/Gold 固定文件覆写，OK 但没有版本化——对参考实现可接受，但**与 Iceberg 的并存会产生叙事上的错位**（"Bronze/Silver=Parquet 文件、Gold=Iceberg 快照"，但 Gold Iceberg 表又被我们自己 DROP 重建）。

#### (P6) 失败/拒绝样本没有治理闭环

- `BronzeWriter.write_rejected` 会把被拒绝的记录写进 `bronze/_rejected/...`。
- 但没有指标、没有告警、没有进入 OpenMetadata 的治理视图；运行时 rejected 记录多了也没人知道。

#### (P7) ECB 选取口径对事件粒度过粗

- `ECBCollector.ENDPOINT` 只取 MRR_RT.LEV（MRO 利率水平）。
- 现代 ECB 主要使用利率是 **Deposit Facility Rate（DFR）**，2022 年之后 MRO 反而不再是主政策工具。
- 这使得 Gold 事件定义（`rate_change_bps != 0`）在近几年变动频次偏低，**对 ML 数据量不友好**。
- 结论上不影响流水线跑通，但影响"端到端得出的模型有意义"的程度。

#### (P8) 运维可见性（SLO/告警）不在 v2.5 范围内

这点是项目自己承认的（`TASKS.md` Block C、`docs/decisions/ADR-010`）。只在"生产就绪"维度列出。

---

## 4. 补充完整的建议

按"影响端到端跑通有效性"的优先级排序。每条都**直接对应上一节的 P#**。

### P1. 让 DAX 成为真正的动态数据源（必要）

**建议 1（最小补法）**：把 DAX collector 改成优先从公开源拉取、失败再回退到 CSV。

示例（新增 `ingestion/collectors/dax_collector.py` 的 `_fetch_live` 分支）：

```python
def _fetch_live(self) -> list[dict[str, Any]] | None:
    """Best-effort pull of DAX daily OHLCV from a free public source.

    Returns None when the live source is unreachable so the caller can
    fall back to the committed sample CSV without failing the pipeline.
    """
    try:
        import yfinance as yf  # optional dependency
    except ImportError:
        return None
    try:
        frame = yf.download("^GDAXI", period="max", progress=False, auto_adjust=False)
    except Exception:
        return None
    if frame is None or frame.empty:
        return None
    frame = frame.reset_index().rename(
        columns={
            "Date": "observation_date",
            "Open": "open_price",
            "High": "high_price",
            "Low": "low_price",
            "Close": "close_price",
            "Volume": "volume",
        }
    )
    return frame.to_dict(orient="records")
```

然后在 `collect()` 里：`raw = self._fetch_live() or self._fetch_data()`，
并在 `requirements.txt` 加 `yfinance` 为 optional。

**建议 2（更稳但更重）**：直接使用 Deutsche Börse / Stooq 历史 CSV URL 作为主来源，保留 committed CSV 作为"airgapped fallback"。

**并在 `README` 和 `ADR-004` 注明**：committed CSV 是用于离线/CI 的 fallback，不等同于真实 DAX 价格序列。

### P2. 让 Iceberg Gold 真正像 Iceberg（强烈建议）

把 `refresh_iceberg_gold_from_hive` 从 `DROP + CTAS` 改为 **幂等 upsert / MERGE**，保留 Iceberg snapshot 历史。示例思路：

```sql
-- 首次初始化
CREATE TABLE IF NOT EXISTS iceberg.gold.ecb_dax_features_iceberg (
    event_date DATE,
    rate_change_bps DOUBLE,
    rate_level_pct DOUBLE,
    is_rate_hike BOOLEAN,
    is_rate_cut BOOLEAN,
    dax_pre_close DOUBLE,
    dax_return_1d DOUBLE,
    dax_return_5d DOUBLE,
    dax_volatility_pre_5d DOUBLE
) WITH (
    partitioning = ARRAY['year(event_date)']
);

-- 每次刷新：按 event_date 做 MERGE
MERGE INTO iceberg.gold.ecb_dax_features_iceberg AS t
USING hive.gold.ecb_dax_features AS s
ON t.event_date = s.event_date
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...;
```

同时在文档/demo 里加一段"Iceberg time travel"验证，比如：

```sql
SELECT * FROM iceberg.gold.ecb_dax_features_iceberg
FOR VERSION AS OF <snapshot_id>;
```

这样 Iceberg 的选型才名副其实。

### P3. 把"今日已摄入"的幂等键从日期换成内容指纹（建议）

在 `BronzeWriter` 里写一个数据内容 `sha256`，同时把"是否重复摄入"的判断改成"当日分区存在且内容指纹一致"：

- 同日 + 相同内容 → skip（当前行为）
- 同日 + 不同内容 → 新增 partition 子键（例如 `run_id=<timestamp>`）并记录 rejected/history
- 这样替换 CSV 立刻能被检测到。

### P4. 补齐 Asset Check，形成最小可用的数据契约（必要）

`TASKS.md` A2 已经预留了位置。建议至少补这四个，并在 `dagster/assets.py` 注册：

1. `gold_features_freshness_check`：max(`event_date`) 与 today 的距离 ≤ 某阈值（例如 180 天）。
2. `silver_ecb_monotonic_check`：Silver ECB 的 `observation_date` 无缺失且严格递增。
3. `silver_dax_gap_check`：Silver DAX 工作日 gap ≤ N 天（例如长假期允许 5 天）。
4. `gold_features_schema_check`：列名/类型与 `register_hive_gold_staging_parquet` 的 DDL 完全一致。

阈值不要写"魔数"，放到 `PipelineConfigResource` 或 `config/quality/*.yaml`。

### P5. Silver/Gold 引入轻量版本化（可选但很有价值）

- Silver：把固定文件路径改成 `silver/<ds>_cleaned/run_date=<today>/part.parquet`，并用 `silver/<ds>_cleaned/_latest.json` 指向"当前 active run"。
- Gold Parquet 层可以在 MinIO 侧用 bucket versioning 兜底（不改代码）。
- 这样 Silver 与 Gold 都具备"回到前一版"能力，对后续 P2 的 Iceberg MERGE 语义也更自然。

### P6. 拒绝样本接入治理闭环（建议）

- 在 Bronze 完成后，如果 `rejected_count > 0`，emit 一个 Dagster metadata 字段 + 一个 structlog 指标 `bronze.rejected.ratio`。
- 在 OpenMetadata 里为 `bronze/_rejected/` 注册一张 Iceberg 表（或 Hive 外表），让目录里能看到"被拒绝的数据"而不是只能看"成功的数据"。
- 在 `tests/integration/` 里加一个"人为注入坏记录"的 case，断言它一定进入 rejected 路径。

### P7. 把 ECB 数据源扩成"多利率"（强烈建议）

把 `ECBCollector.ENDPOINT` 从单一 MRO 扩为至少 3 条 series：

- MRO (`MRR_RT.LEV`)：主再融资
- DFR (`DFR.LEV`)：Deposit Facility Rate（2022 年后真正的政策利率）
- MLF (`MLF.LEV`)：Marginal Lending Facility

并让 `silver_to_gold_features.build_gold_features` 可以按任意一条 rate series 派生事件（通过参数传入 rate 列名）。这会让 2022–2025 的事件变得丰富得多，直接改善 Gold 的可用行数和 ML 的统计意义。

### P8. 最小可运维补丁（可选，属 v3 范围但值得前置一小步）

在不等 v3 的前提下，可以先做两件小事：

1. 在 `_emit_metric` 里把 `pipeline.step.duration_ms` 同时写入一张 Iceberg 运维表 `iceberg.ops.pipeline_metrics`，这样 Superset 里可以直接建"每日步骤耗时"图。
2. 把 `gold_features_min_rows_check` 的阈值从硬编码 10 提到 config，并在 README 的 "运行后验证"里加一段 `trino` CLI 查询清单（ECB/DAX/Gold 最新 `event_date`、行数、以及 Iceberg 最新 snapshot 数）。

---

## 5. 一张"如果只做三件事"的清单

如果只有精力做三件事来显著提升"端到端跑通的可信度"，按顺序推荐：

1. **P1 — 接入真实 DAX 源（yfinance 或等价）**，并在文档里明确"committed CSV 仅作 airgapped fallback"。
2. **P2 — 把 Iceberg Gold 的 `DROP + CTAS` 改成 `CREATE IF NOT EXISTS + MERGE`**，并增加一条演示 time travel 的 SQL。
3. **P4 + P7 — 加三条 Asset Check（freshness/schema/monotonic）+ 把 ECB 源扩成 MRO/DFR/MLF 三条**。

完成这三件事后，项目可以合理地声明"v2.5 基线下 DAX+ECB 真正意义上的端到端可信运行"。

---

## 6. 对项目当前版本定位的建议措辞

目前 `README.md` 与 `docs/roadmap.md` 把 v2.5 描述为"production-minded lakehouse reference implementation"。结合上述评估，更严谨的措辞建议为：

> v2.5 is a **reference-grade runnable lakehouse** with medallion separation, open table format at the Gold layer, unified metadata, orchestrated assets with basic data-quality gating, and tracked ML experimentation. It is **not yet production-grade**: multi-environment deployment, secrets/access governance, SLO-driven observability, Iceberg snapshot discipline, and a non-synthetic DAX source are tracked as v2.5+/v3 work.

这个措辞与 `TASKS.md` 的 Block A–G、`ADR-007`–`ADR-012` 保持一致，且不会让读者产生"已经可以上生产"的误读。

---

## 7. 计算层演进建议（dbt / PySpark / Trino 角色重划）

> 本节回答一个后续提问："转换计算部分能否换成 dbt 或 PySpark，让 Trino 只负责查询？"
> 完整决策记录见 **[ADR-016: Compute engine migration](decisions/ADR-016-compute-engine-migration.md)**，本节是面向读者的摘要。

### 7.1 概念先分清

- **dbt 本身不是计算引擎**，它是 SQL 转换编排框架，必须绑定一个底座（`dbt-trino` / `dbt-spark` / `dbt-duckdb`）。
- **PySpark 是真正的计算引擎**，可以直接读写 MinIO 上的 Parquet 和 Iceberg。
- 因此"换成 dbt 或 PySpark"其实是三个候选：
  - **组合 A：`dbt-trino`** → Trino 同时做计算和查询，**不满足"Trino 只负责查询"的约束**。
  - **组合 B：`PySpark` + Iceberg** → Spark 计算，Trino 纯查询（满足约束）。
  - **组合 C：`dbt-spark` + Iceberg** → Spark 计算，dbt 做 SQL-first 编排，Trino 纯查询（满足约束，且 SQL 化/血缘/测试更完整）。

### 7.2 推荐路线：分两阶段过渡到组合 C

**阶段 1 —— 引入 Spark + Iceberg 写入，Trino 变为只读**

- `docker-compose.yml` 新增单机 Spark（master + 1 worker，带 Iceberg 1.5+ runtime jar，共用现有 Hive Metastore）。
- 用 PySpark 重写 `silver_to_gold_features`，Gold 通过 `MERGE INTO iceberg.gold.ecb_dax_features` 按 `event_date` upsert，保留 Iceberg 快照历史。
- 删除 `ingestion/trino_sql.py::refresh_iceberg_gold_from_hive` 以及其 Hive staging 表——**Trino 从此不再执行写入 DDL/DML**。
- `ml/evaluate.py`、Superset、OpenMetadata 全部不用改，仍然经 Trino 读 `iceberg.gold.*`。

阶段 1 完成后即满足"Trino 只负责查询"的硬约束，并且上一份评估里的 **P2（Iceberg 快照丢失）** 直接消失。

**阶段 2 —— 引入 `dbt-spark` 接管 Silver/Gold 的 SQL 化和测试**

- 在 `transformations/dbt/` 建立 dbt 项目，适配器用 `dbt-spark`（Thrift / Spark Connect）。
- 把 `ecb_bronze_to_silver` / `dax_bronze_to_silver` / PySpark 的 Gold 作业改写为 dbt model（`incremental` + `unique_key`）。
- 通过 `dagster-dbt` 让每个 dbt model 自动映射为 Dagster asset，原有的资产依赖图形状保持不变。
- 使用 dbt 自带的 `not_null` / `unique` / `accepted_values` 以及自定义 freshness 测试，**顺带补齐** 评估报告里的 **P4（asset check 密度不足）**。
- 开启 OpenMetadata 的 dbt manifest ingestion，让 Silver/Gold 血缘和测试结果直接出现在数据目录中，**呼应 TASKS.md Block A**。

### 7.3 Bronze 为什么保留 Python

Collector 的职责是"和外部数据源对话 + Pydantic 校验 + 拒绝样本写出"，这既不是 SQL 形态的工作，也不应该被 dbt/Spark 强行吸收。保持 `ingestion/collectors/*.py` 不动，可以让"外部世界 ↔ Lakehouse"的边界保持清晰、单一来源。

### 7.4 成本与风险快照

| 维度 | 现状 | 阶段 1 后 | 阶段 2 后 |
|------|------|----------|----------|
| Docker 镜像体量 | 小 | 明显增大（+Spark） | 再增（+dbt image / Spark Thrift） |
| Cold-start 时间 | 秒级 | 数十秒（JVM） | 数十秒 |
| Trino 角色 | 计算+查询 | **仅查询** | **仅查询** |
| Iceberg 快照 | 每次丢失 | 保留（MERGE） | 保留 |
| Asset check / dataset test 密度 | 低 | 中（仍需手写） | 高（dbt test + Dagster check） |
| OpenMetadata 血缘 | Trino 扫描 | Trino 扫描 | Trino 扫描 + dbt manifest |
| 回滚难度 | — | 低（恢复 `.py` 和 CTAS 即可） | 低（把 Dagster asset 切回阶段 1 的 PySpark job） |

### 7.5 与 v3 路线的关系

- 阶段 1 属于 "v2.5 延伸" 合理范围，因为它不改变部署拓扑的根本假设（仍是 Docker Compose），只把计算角色分到 Spark。
- 阶段 2 可以落在 v2.5 延伸或 v3 前置工作，具体落点取决于是否与 `TASKS.md` Block A（governance contracts）合并推进。若合并推进，dbt 测试 + OpenMetadata 血缘能成为 governance baseline 的事实载体。

### 7.6 本节推荐的最小落地顺序

1. ADR-016 接收评审（本仓库已提交为 **Proposed**）。
2. 做 Phase 1 的一次端到端 PR：Spark 容器 + PySpark Gold 作业 + 删掉 Trino 写路径。
3. 在 Phase 1 合并后再做 Phase 2：`dbt-spark` 项目初始化 + Silver 两个 model 先行 + dbt tests。
4. Phase 2 合并后更新 README 的"What this project is"段落，改用"Spark writes Iceberg, Trino serves queries"的新一句话概括。

## 附录 A：本次评估所涉文件

- `README.md`
- `Makefile`
- `docker/docker-compose.yml`
- `dagster/assets.py`, `dagster/definitions.py`
- `ingestion/collectors/ecb_collector.py`, `ingestion/collectors/dax_collector.py`
- `ingestion/schema/ecb_schema.py`
- `ingestion/trino_sql.py`
- `transformations/ecb_bronze_to_silver.py`
- `transformations/dax_bronze_to_silver.py`
- `transformations/silver_to_gold_features.py`
- `ml/train_ecb_dax_model.py`, `ml/evaluate.py`
- `data/sample/dax_daily_sample.csv`（2000-01-03 ~ 2024-12-31，6522 行）
- `docs/architecture.md`, `docs/roadmap.md`, `TASKS.md`

## 附录 B：本报告与现有 TASKS.md 的对应关系

| 本报告建议 | TASKS.md 对应块 |
|------------|----------------|
| P1（DAX 真实数据源） | （目前未覆盖，建议加入 Block A 的 "source-of-truth" 定义条目） |
| P2（Iceberg MERGE 化） | A1（`ecb_dax_features_iceberg` 的治理契约）+ 新增技术债 |
| P3（内容指纹幂等键） | A1 quality_class + A2 quality gate |
| P4（Asset Check 扩展） | A2（quality gate tightening） |
| P5（Silver/Gold 版本化） | A1 + B3（rollback readiness 的数据侧） |
| P6（拒绝样本治理） | A1 + A2 |
| P7（ECB 多利率） | A1（dataset governance baseline 的 business_purpose） |
| P8（运维指标先行） | C1 / C2 的轻量前置 |
| §7 计算层演进（dbt-spark + Spark + Iceberg） | 跨 Block A / Block F，见 [ADR-016](decisions/ADR-016-compute-engine-migration.md) |
