# SoloLakehouse Daily Operations Handbook

**One document for steady Compose operation.**  
Use this after development features have landed and the goal is *keep it running*,
not *add engines*.

| | |
|---|---|
| **Audience** | Solo operator / small team on the reference Compose stack |
| **Runtime** | v2.5 baseline (Dagster + Iceberg + Trino + OM + Superset + MLflow) |
| **Not for** | Kubernetes cutover, new data domains, streaming/crypto Phase 2 |
| **Deep incident commands** | [`RUNBOOK.md`](../RUNBOOK.md) |
| **Backup / restore detail** | [`entity-backup-restore-runbook.md`](entity-backup-restore-runbook.md) |
| **What to demo** | [`capability-showcase-guide.md`](capability-showcase-guide.md) |
| **Hardening backlog** | [`TASKS.md`](../TASKS.md) Block `K` |

Authority for *what ships next* remains `docs/roadmap.md` + `TASKS.md`.

---

## 1. Operating posture (read once)

Success in this phase means:

1. Weekday **06:00 UTC** `full_pipeline_job` stays green  
2. Data freshness is within contract / sensor expectations  
3. Audit bucket gets lineage (and model) evidence for successful runs  
4. `make verify` is green, and failures can reach a human  
5. You have a **dated** backup + restore drill before claiming recoverability  

Do **not** treat new domains, new engines, or K8s as ops success metrics.

---

## 2. Duty card — first five minutes when something feels wrong

```bash
# 1) Health
make verify
make health          # portal: http://127.0.0.1:8090/health
docker ps --format 'table {{.Names}}\t{{.Status}}'

# 2) Today’s pipeline
# Dagster UI: http://127.0.0.1:3000  → runs → full_pipeline_job

# 3) Logs (pick the unhealthy service)
docker logs --tail 200 slh-dagster-daemon
docker logs --tail 200 slh-trino
docker logs --tail 200 slh-hive-metastore
docker logs --tail 200 slh-postgres
```

**Escalate only after:** verify output saved, failing container name known, last
Dagster run id copied (if any).

Targeted restart (then re-verify):

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.openmetadata.yml \
  -f docker/docker-compose.superset.yml \
  restart <service>
make verify
```

Destructive reset (`make clean`) wipes `docker/data/` — **not** a routine ops
action.

---

## 3. Cadence checklist

### Every weekday (≈10 minutes)

- [ ] Dagster: `full_pipeline_job` **SUCCESS** after 06:00 UTC  
- [ ] Note run id: `____________________`  
- [ ] Bronze/Silver freshness sane (ECB ~T+0 business day; EWG often T+1)  
- [ ] Rejected-record spike? (expect empty / near-empty)  
- [ ] Audit bucket has objects under  
      `lineage/<dataset_id>/<YYYY-MM-DD>/<run_id>/`  
      at least `manifest.json` for governed assets (and model-evidence for ML)  
- [ ] No open “red” on http://127.0.0.1:8090/health  

**Pass rule:** pipeline green + verify green (or known waived limitation documented).

### Weekly (≈20 minutes)

- [ ] `make verify`  
- [ ] Optional: `make operational-evidence` (keep output / path)  
- [ ] Disk: free space on volume hosting `docker/data/` (postgres + minio grow)  
- [ ] OpenMetadata token still usable **or** admin-password refresh path works  
- [ ] Glance sensors: freshness, lineage_evidence, email success/failure  

### Monthly

- [ ] `make secrets-discipline`  
- [ ] Rotate or confirm: OM JWT / admin password, DB, MinIO, Alpha Vantage key  
- [ ] Confirm Dagster image matches `main` (no leftover hot-patches)  
- [ ] Skim Block `K` progress; do not silently expand scope  

### Quarterly

- [ ] Full backup with **quiesce** (no in-flight Dagster run) — see backup runbook  
- [ ] Restore drill on a disposable target; file under `docs/restore-drills/`  
- [ ] Re-state accepted risks: loopback-only access, OM = re-ingest not MySQL restore  

---

## 4. What “good” looks like (quick reference)

| Signal | Healthy | Investigate |
|--------|---------|-------------|
| Dagster schedule | Weekday SUCCESS ~30–90s | FAILURE, missing run, >few minutes |
| ECB observation date | Today or last business day | Multi-day lag vs freshness SLA |
| EWG observation date | Often yesterday (T+1) | Stuck >2–3 business days |
| Gold event-study rows | Stable count until next rate event | Sudden drop to empty |
| Lineage manifests | Present for run id | Missing → OM token/owner/sensor |
| `make verify` | Exit 0 | Any red service |
| Disk | Comfortable headroom | <20% free on data volume (treat as incident) |

UI map:

| Surface | URL |
|---------|-----|
| Health | http://127.0.0.1:8090/health |
| Dagster | http://127.0.0.1:3000 |
| Trino | http://127.0.0.1:8080 |
| MinIO | http://127.0.0.1:9001 |
| OpenMetadata | http://127.0.0.1:8585 |
| MLflow | http://127.0.0.1:5000 |
| Superset | http://127.0.0.1:8088 |

---

## 5. Fault classes — what to do

### A. Pipeline failed (Dagster FAILURE)

1. Open run → failed asset / error message  
2. Classify: source API / validation / Iceberg write / downstream transform / ML  
3. Fix or wait (Alpha Vantage quota, ECB outage)  
4. Re-run: `make pipeline` or Dagster launch of `full_pipeline_job`  
5. Keep run id + error snippet in the ops log  

Email sensors may already notify on failure/success — confirm delivery path is
monitored.

### B. Services unhealthy / exited

1. `docker ps -a` — who exited?  
2. `docker logs --tail 200 <name>`  
3. `restart` that service; `make verify`  
4. Host reboot: Compose `restart: unless-stopped` should bring long-runners back;
   still run `make verify`  

### C. Data present but “stale”

1. Check freshness sensor skip reasons in Dagster  
2. Confirm collector actually ran (bronze materialization metadata)  
3. Calendar gaps (weekends / US holidays for EWG) are expected — do not “fix”
   by force-loading retired sample CSV  

### D. Lineage / audit evidence missing

Checklist in order:

1. Pipeline actually **SUCCESS**?  
2. `OPENMETADATA_AUTH_TOKEN` usable? If expired, refresh via login /  
   `OPENMETADATA_ADMIN_PASSWORD` (emission uses `resolve_bearer_token`)  
3. OM tables have **owners**? Adapter fails closed if owners empty  
4. Sensor `lineage_evidence_sensor` RUNNING?  
5. Backfill:

```bash
make lineage-evidence \
  DATASET_ID=fin.ecb_german_equity_proxy_features_gold \
  DAGSTER_RUN_ID=<run-id>
```

Evidence commands must **fail loudly** and write nothing when a source is
missing — that is correct behavior.

### E. Disk full / MinIO or Postgres errors

1. Stop non-essential load; do **not** keep forcing pipeline  
2. Free space or expand volume under `docker/data/`  
3. After space returns: `make verify`, then one controlled pipeline  

(Block `K5` adds disk checks to verify — until then, weekly manual check.)

### F. OpenMetadata / catalog weirdness

- Prefer `make om-ingest-trino` to refresh Trino metadata  
- Restore path for OM is **re-ingest**, not “restore MySQL and pray”  
- UI alone is not the audit trail — audit objects in MinIO are  

---

## 6. Evidence & audit — operator paths

Audit bucket (default): `sololakehouse-audit`

```text
lineage/<dataset_id>/<UTC-date>/<dagster_run_id>/manifest.json
lineage/<dataset_id>/<UTC-date>/<dagster_run_id>/model-evidence/<mlflow_run_id>.json
```

Useful commands:

```bash
make verify
make validate-contracts
make lineage-evidence DATASET_ID=... DAGSTER_RUN_ID=...
make operational-evidence
make secrets-discipline
make promotion-evidence
make rollback-drill
```

Env discipline:

- Edit `.env.shared` / `.env.secrets`, then `make init-env`  
- Never rely on hand-edited `.env` surviving the next merge  
- Never commit secrets  

---

## 7. Backup & restore (ops minimum)

Before claiming recoverability:

1. **Quiesce** — no in-flight Dagster run  
2. Backup per [`entity-backup-restore-runbook.md`](entity-backup-restore-runbook.md)
   (Postgres logical dumps + MinIO mirrors + `.env` secrets handling)  
3. Restore on a **disposable** target  
4. Validate with `make verify` and a pipeline/demo path  
5. Record the drill (date, git SHA, what worked, OM = re-ingest)  

Until Block `K9`/`K10` are scripted and drilled, say:

> “Backup procedure exists in docs; full restore drill is still an open
> hardening item.”

---

## 8. Secrets, tokens, and access

| Item | Ops note |
|------|----------|
| OM JWT | Short-lived if from login; keep admin password in `.env.secrets` for refresh |
| Weak defaults | Replace example passwords before any non-loopback exposure |
| Network | Loopback binds + tunnel are the accepted model near-term |
| Alpha Vantage | Daily quota — collector failures may be rate limits |

---

## 9. Change control during operations

**Allowed without a new Owner Decision**

- Block `K` hardening (reliability, backup, alert, ADRs)  
- Bugfixes that preserve `make demo` / `make pipeline`  
- Docs/runbook clarity  

**Needs Owner Decision before work**

- New domain (FRED, electricity, aviation, …)  
- L4 Phase 2 streaming/crypto  
- Starting v3.0 / Kubernetes  
- Portal/Keycloak into the default Compose stack (gate D3)  

**Never**

- Revive `data/sample/dax_daily_sample.csv` as a market-leg fallback  
- Emit partial evidence bundles  
- Claim compliance / WORM certification / production-readiness without records  

---

## 10. Tiny ops log template (copy per day)

```text
Date (UTC):
Pipeline run id:
Status: SUCCESS | FAILURE
Freshness notes (ECB / EWG):
Evidence: manifests OK | missing (reason)
Verify: OK | fail (service)
Actions / follow-ups:
```

Keep these somewhere durable (even a local folder). They are what turn
“I think it’s fine” into operable history.

---

## 11. Related docs

| Doc | Use when |
|-----|----------|
| [`RUNBOOK.md`](../RUNBOOK.md) | Service restart, logs, Trino debug, clean slate |
| [`entity-backup-restore-runbook.md`](entity-backup-restore-runbook.md) | Backup set and restore order |
| [`operational-slo.md`](operational-slo.md) | SLO framing |
| [`governance-evidence-layout.md`](governance-evidence-layout.md) | Manifest layout / Object Lock |
| [`capability-showcase-guide.md`](capability-showcase-guide.md) | External walkthrough |
| [`TASKS.md`](../TASKS.md) Block `K` | What to harden next |
| [`DEMO.md`](../DEMO.md) | Cold-start recording script |

---

## 12. One-line summary

> **Weekdays: confirm pipeline + evidence. Weekly: verify + disk + tokens.
> Quarterly: backup and restore for real. Change the platform only through
> Block `K` or a fresh Owner Decision — not through quiet scope creep.**
