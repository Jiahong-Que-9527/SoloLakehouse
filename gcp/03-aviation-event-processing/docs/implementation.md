# Aviation Event Processing implementation plan

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

**Status:** accepted. [Project brief](../README.md) and [technical design](design.md).

**Sequence steps 1–5 complete; first delivery accepted 2026-11-21.** The
live acceptance record — fixture-to-state reconciliation, transient
failure, crash after commit, dead-letter routing and replay — is in
[`cloud-verification.md`](cloud-verification.md). The delivery trail and
the one apply failure (log-metric visibility race at the alert policy)
are recorded there as well.

**Sequence steps 1–2 done (2026-11-21, local only).** The expected state was
written as fixtures first; the reducer contract is implemented and tested
against them — envelope validation (`envelope.py`), the pure decision table
including the unknown-type rule (`reducer.py`), an explicit-buffer
transactional store with injectable commit failures (`store.py`), the
parse → dedup → decide → commit → ack consumer with quarantine and
dead-letter routing (`consumer.py`), and two seeded batches whose final
state is identical for every tested seed (`generator.py`, 61 tests, project
CI workflow added).

**Infrastructure bootstrapped, plan verified, nothing applied (2026-11-21).**
The cloud delivery pieces are now written and tested: the one-script
BigQuery decision store, the Pub/Sub puller/publisher/dead-letter adapters
and the on-demand drain job (`cloud_gcp.py`, `job.py`, `publisher.py`,
`replay.py`, Dockerfile, 81 tests) plus the G03 cloud workflow mirroring
the G01/G02 playbook. Bootstrap ran with the owner's approval — registry
created and imported, `roles/pubsub.admin` granted, the already-enabled
Pub/Sub service imported — and `terraform plan` against the real state
shows **22 to add, 0 to change, 0 to destroy** (free-tier SKUs only;
as-built in [`infra/BOOTSTRAP.md`](../infra/BOOTSTRAP.md)). What remains:
open the PR for the plan-only CI job, merge, approve the `gcp-test` gate
so CI builds the image and applies, then run steps 4–5 (transient-failure
and interruption drills, replay exercises) against the live resources and
record them in a `cloud-verification.md`.

## First delivery

Use two independently seeded batches, one for synthetic airport operations and one for synthetic energy revisions. Deliver a reconciled final state and a replayable failure record for each.

## Implementation sequence

1. Write the expected state before publishing. For one entity send revision 2, a second delivery of its event ID, revision 1, then a conflicting revision 2 under a new ID. Expect revision 2 to remain current, one accepted business change and one conflict. Add a malformed envelope and a valid correction.

2. Test the reducer locally. Separate envelope validation, event-ID deduplication and revision comparison. Decide how unknown types are recorded. Persist the receipt, history outcome and state mutation in an explicit transaction. Acknowledge only after the commit succeeds.

3. Deploy a bounded pull consumer and isolated Pub/Sub and BigQuery resources. For the first exercise run a single consumer with one in-flight write. Record the concurrency limit as part of the evidence. Concurrent writers require a separately tested serialization or contention strategy.

4. Inject transient write failure and interruption after commit but before acknowledgement. Reconcile receipt counts and entity state after redelivery. Route invalid payloads with their reason to quarantine, confirm durable routing before acknowledging, and record any repeated failure notifications.

5. Exercise replay twice. For a transient failure reuse the same envelope. For a malformed message retain the original failure record and correlate the corrected envelope with it. Verify that replay of an already applied ID has no additional effect. Stop the consumer after draining the test batch and inspect backlog and final rows.

## Acceptance record

A fixture-to-state reconciliation with message IDs, applied and ignored revisions, retry outcomes and a dead-letter recovery. State the tested execution and concurrency conditions alongside any idempotency claim. Link the run record from the project brief after execution and identify any checks still pending.
