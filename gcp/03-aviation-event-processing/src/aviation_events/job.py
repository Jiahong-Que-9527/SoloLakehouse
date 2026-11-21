"""Cloud Run job entrypoint: drain the pull subscription, then exit.

Flow per delivery (design section 5, mirrored from consumer.py):
- unparseable body: quarantine row first (durable evidence), then publish
  to the dead-letter topic, then ack;
- parseable body: ONE BigQuery script decides and writes; ``redelivered``
  is an acknowledgement with no further write; a conflict publishes the
  original body to the dead-letter topic (the script already receipted,
  recorded and quarantined it), everything else is a plain ack;
- a warehouse error propagates: the caller nacks and the subscription
  redelivers.

One task runs this loop strictly sequentially — one in-flight write,
matching the recorded concurrency limit of the first exercise.
"""

import os
from datetime import UTC, datetime

from aviation_events.cloud_gcp import BigQueryEventStore, PubSubDeadLetters, PubSubPuller
from aviation_events.envelope import EnvelopeError, parse_envelope
from aviation_events.reducer import KNOWN_EVENT_TYPES, OUTCOME_CONFLICT
from aviation_events.store import TransientError

ACK = "ack"
NACK = "nack"
DEAD_LETTERED = "dead_lettered"


class EventJob:
    """Wires the cloud store, puller and dead-letter topic into one loop."""

    def __init__(self, store, puller: PubSubPuller, dead_letters) -> None:
        self._store = store
        self._puller = puller
        self._dead_letters = dead_letters

    def process(self, body: bytes, message_id: str, received_at: datetime) -> str:
        """Handle one delivery; returns the ack decision for the caller."""
        try:
            return self._process(body, message_id, received_at)
        except TransientError:
            return NACK

    def _process(self, body: bytes, message_id: str, received_at: datetime) -> str:
        try:
            event = parse_envelope(body)
        except EnvelopeError as error:
            self._store.record_quarantine(
                message_id, error.reason, body.decode("utf-8", errors="replace"), received_at
            )
            self._dead_letters.publish(body, error.reason)
            return DEAD_LETTERED

        outcome, reason = self._store.commit_delivery(
            event,
            message_id,
            received_at,
            moves_state=event.event_type in KNOWN_EVENT_TYPES,
            body=body,
        )
        if outcome == OUTCOME_CONFLICT:
            self._dead_letters.publish(body, reason)
            return DEAD_LETTERED
        # 'redelivered' (committed id) and applied/ignored/duplicate/stored
        # are all plain acknowledgements with no further write.
        return ACK

    def drain(self, max_messages: int, *, batch_size: int = 10) -> dict:
        """Pull-process-ack until the backlog empties or the cap is reached."""
        processed = 0
        nacked = 0
        dead_lettered = 0
        while processed < max_messages:
            batch = self._puller.pull_batch(min(batch_size, max_messages - processed))
            if not batch:
                break  # drained
            for delivery in batch:
                if processed >= max_messages:
                    break  # leave the excess delivery unacked; it redelivers later
                received_at = datetime.now(UTC)
                status = self.process(delivery.body, delivery.message_id, received_at)
                processed += 1
                if status == NACK:
                    nacked += 1
                    self._puller.nack([delivery.ack_id])
                    continue
                if status == DEAD_LETTERED:
                    dead_lettered += 1
                self._puller.acknowledge([delivery.ack_id])
        return {"processed": processed, "nacked": nacked, "dead_lettered": dead_lettered}


def main() -> int:
    subscription = os.environ["PUBSUB_SUBSCRIPTION"]
    dataset = os.environ["BQ_DATASET"]
    dead_letter_topic = os.environ["PUBSUB_DLQ_TOPIC"]
    max_messages = int(os.environ.get("MAX_MESSAGES", "10"))

    job = EventJob(
        store=BigQueryEventStore(dataset),
        puller=PubSubPuller(subscription),
        dead_letters=PubSubDeadLetters(dead_letter_topic),
    )
    summary = job.drain(max_messages)
    print(f"drain summary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
