"""Message-level flow (design section 5): parse, dedup, decide, commit, ack.

One :meth:`EventConsumer.process` call handles one Pub/Sub delivery.
Acknowledgement happens only after the store transaction commits:

- redelivery of a committed ``event_id`` -> ack with no further write
  (rule 1); this makes a crash between commit and ack harmless;
- permanent failures (invalid envelope, conflicting revision) commit
  their durable evidence first — the quarantine row, plus receipt and
  history for a parseable body — then publish to the dead-letter sink,
  then ack. If the dead-letter publish fails the message is nacked and
  the redelivery resolves through the receipt; recovery then goes by
  replaying from the quarantine record rather than the dead-letter
  topic;
- transient failures (warehouse unavailable) nack with no write; the
  subscription redelivers and the next attempt runs the same script.

A pull consumer runs with one in-flight write for the first exercise
(sequence step 3), so no serialization strategy is implemented here.
"""

from dataclasses import dataclass
from typing import Protocol

from aviation_events.envelope import EnvelopeError, parse_envelope
from aviation_events.reducer import decide
from aviation_events.store import Clock, TransientError, system_clock

ACK = "ack"
NACK = "nack"
DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True)
class Outcome:
    """What the caller should do with the delivery, and why."""

    status: str
    reason: str | None = None


class DeadLetterSink(Protocol):
    """The dead-letter topic; the cloud delivery publishes envelopes to it."""

    def publish(self, body: bytes, reason: str) -> None: ...


class FakeDeadLetterSink:
    """In-memory sink recording published bodies; can fail transiently."""

    def __init__(self, *, failures: int = 0) -> None:
        self.published: list[tuple[bytes, str]] = []
        self._failures = failures

    def publish(self, body: bytes, reason: str) -> None:
        if self._failures > 0:
            self._failures -= 1
            raise TransientError("simulated dead-letter publish failure")
        self.published.append((body, reason))


class EventConsumer:
    """Folds deliveries into the store through one transaction each."""

    def __init__(self, store, dead_letters: DeadLetterSink, *, clock: Clock | None = None) -> None:
        self._store = store
        self._dead_letters = dead_letters
        self._clock = clock or system_clock

    def process(self, body: bytes, message_id: str) -> Outcome:
        try:
            return self._process(body, message_id)
        except TransientError as error:
            return Outcome(NACK, str(error))

    def _process(self, body: bytes, message_id: str) -> Outcome:
        try:
            event = parse_envelope(body)
        except EnvelopeError as error:
            return self._quarantine_unparsed(body, message_id, error.reason)

        with self._store.transaction() as tx:
            if tx.receipt_exists(event.event_id):
                return Outcome(ACK)  # rule 1: committed id, no further write
            state = tx.fetch_state(event.entity_id)
            decision = decide(event, state)
            tx.record_receipt(event, decision.outcome, message_id, self._clock())
            if decision.state is not None:
                tx.put_state(decision.state)
            if decision.dead_letter:
                tx.record_quarantine(
                    message_id, decision.reason or decision.outcome, _decode(body), self._clock()
                )

        if decision.dead_letter:
            return self._publish_dead_letter(body, decision.reason or decision.outcome)
        return Outcome(ACK)

    def _quarantine_unparsed(self, body: bytes, message_id: str, reason: str) -> Outcome:
        """Record the failure durably, then route the body to the dead-letter sink."""
        with self._store.transaction() as tx:
            tx.record_quarantine(message_id, reason, _decode(body), self._clock())
        return self._publish_dead_letter(body, reason)

    def _publish_dead_letter(self, body: bytes, reason: str) -> Outcome:
        self._dead_letters.publish(body, reason)
        return Outcome(DEAD_LETTERED, reason)


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")
