# Cloud verification — G03 Aviation Event Processing

<!-- [Kimi·2026-11-21] Acceptance evidence for the first cloud delivery,
recorded live against project slh-gcp-test, region europe-west3, with the
owner's standing cost-gate authorization (free-tier SKUs only). -->

## What was proven

Synthetic airport and energy events flow from a seeded generator through a
Pub/Sub pull subscription into one transactional BigQuery decision script
and land as one current state per entity. The live run exercised the full
design section 7 matrix: duplicate deliveries collapse to one receipt,
revisions win by value rather than arrival order, equal-revision
conflicts are quarantined and dead-lettered, unknown types are stored
without moving state, a simulated warehouse failure recovers through
subscription retry, a crash between commit and ack is harmless on
redelivery, a poison message is dead-lettered by the subscription policy
itself, and replay of committed IDs has no additional effect.

## Delivery trail

| Step | Evidence |
|---|---|
| Plan (approved by owner) | PR #203; CI plan job: `Plan: 22 to add, 0 to change, 0 to destroy` |
| First apply — alert policy failed | run 44898222374, apply 45s: the log-based metric created 20 s earlier was not yet visible to Cloud Monitoring ("up to 10 minutes"). All other 21 resources applied. |
| Apply rerun — full stack up | same run, job 136837018330, apply green 23s after the deployment was re-approved |
| Gate approvals | deployments `7962568306`, `7962942731` (environment `gcp-test`, required reviewer) |
| Consumer image | `europe-west3-docker.pkg.dev/slh-gcp-test/aviation-events/aviation-event-consumer:c1a27089` |

Deployed surface: topics `aviation-events` + `aviation-events-dlq`
(europe-west3 storage policy), subscriptions `aviation-events-pull`
(pull, ack deadline 30s, retry backoff 10s–600s, dead-letter policy
`max_delivery_attempts=5`, retention 7 days) + `aviation-events-dlq`,
dataset `aviation_events` with tables `event_receipt`, `entity_state`,
`event_history`, `event_quarantine`, Cloud Run job
`aviation-event-consumer` (1 task, parallelism 1, `MAX_MESSAGES=10`,
`max_retries=0`), runtime SA `aviation-events-runtime`, log metric and
error alert.

## Bootstrap record (G03 deltas, one-time, outside Terraform)

`infra/BOOTSTRAP.md`, executed 2026-11-21 **before** the first merge:

- Registry `aviation-events` created via `gcloud` and `terraform import`ed
  into the G03 state prefix.
- Deployer SA granted `roles/pubsub.admin` (G01's grant set predates
  Pub/Sub).
- `pubsub.googleapis.com` was already enabled, so the service resource was
  imported with the `{project}/{service}` ID instead of being created.
- The Pub/Sub service agent already existed; no warm-up needed.

## Execution conditions

Every non-fault delivery was processed by the deployed Cloud Run job
(executions `gcn8k`, `wmq5c`, `vzmj5`, `hw54l` — 26 deliveries total,
drained sequentially). The fault-injection drills ran the same
`EventJob` flow locally against the live Pub/Sub and BigQuery resources,
because the injection point is the warehouse call itself; delivery
counts below include them. One consumer, one in-flight write, no second
publisher during the exercises — the recorded concurrency limit for
these results.

## Acceptance matrix (design section 7)

| Case | Required result | Live result |
|---|---|---|
| Same `event_id` delivered twice (fixture `evt-456-b`) + replay of applied ids | One receipt, one state change | 1 receipt, 1 history row; replayed copy acked as `redelivered`, no write |
| Higher revision arrives first, then older ones | State stays on the higher revision | `LH789`: rev 4 applied, revs 1–3 ignored; `DE\|...\|00:30`: rev 3 applied first, 1–2 ignored |
| Missing required field (`evt-456-e`) | No state change, quarantine row, dead-letter | history empty for the raw body; quarantine `missing_field:payload`; DLQ message `21973415899238379` |
| BigQuery unavailable once | Nack, then applied exactly once on retry | first attempt `nack`, redelivery after ~40s, `ack`, 1 receipt (`evt-drill-transient`) |
| Crash after commit before ack | Redelivery acks with no further write | commit succeeded, no ack; redelivery `redelivered` → ack; 1 receipt (`evt-drill-crash`) |
| Poison message | Dead-lettered after the retry limit | after 6 failed deliveries the subscription policy moved it to the DLQ itself: message `21968286562176763` with `CloudPubSubDeadLetterSourceDeliveryCount: 5` |
| Replay of an already applied/conflicted ID | State unchanged | replay command republished both conflict bodies; both acked with no new rows |
| Corrected envelope correlates with the failure record | Recovery closes the loop | corrected `evt-456-e` (same event_id, payload added) parsed, receipted and **ignored** — rev 2 < the stored rev 3 correction, exactly per the revision rules |
| Energy revision fixture | Expected final value per interval | `{"value":40125.5}`, `{"value":39800.0}`, `{"value":40350.0}` — all three match |
| Unknown event type | Stored, no state move | `evt-789-z` (`baggage_loaded`, rev 5): receipt + history `stored`; `entity_state` untouched |

## Final reconciliation (BigQuery)

After all exercises — 24 distinct event_ids, all accounted for:

- `event_receipt`: **24 rows** — applied 13, ignored 7, conflict 2,
  duplicate 1, stored 1. Redeliveries added no rows (receipt dedup by
  `event_id`).
- `entity_state`: **8 rows**, every value as expected (three airport
  legs at the winning revision, two drill entities, three energy
  intervals with the exact corrected values above).
- `event_history`: **24 rows**, one per receipted delivery.
- `event_quarantine`: **4 rows**, keyed by delivery and reason — the
  original malformed body and its replayed copy are separate deliveries
  by design (different Pub/Sub message IDs, `occurrences=1` each), plus
  the two revision conflicts.

Dead-letter message IDs recorded: `23361562359445434` (energy conflict),
`21973415899238379` (malformed original), `22650163461462754` (airport
conflict), `21968286562176763` (poison, policy-forwarded).

## Cost

All SKUs are Free Trial-covered free-tier resources: ~30 KB of Pub/Sub
traffic, four Cloud Run job executions of a few seconds, BigQuery
storage in the low megabytes and a handful of small queries. Recorded
spend: **€0.00**; no plan ever showed a destroy.

## What was not exercised

Throughput, ordered delivery (the design explicitly does not require
it), concurrent consumers (the v1 exercise runs one), and Cloud
Monitoring alert firing (the alert exists; no error was produced to
trigger it). These are out of the G03 v1 scope by design.
