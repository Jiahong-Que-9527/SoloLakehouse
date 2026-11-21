"""Thin Google Cloud adapters for the G03 event path.

Client libraries are imported lazily so the core package and its tests run
without the `cloud` extra installed (G01 pattern). Credentials come from the
environment: Application Default Credentials locally, the job's service
account in Cloud Run.

Per the design, ONE BigQuery script performs the whole decision for a
delivery — receipt check, revision comparison, and every write — inside one
transaction. The Python side only renders, runs and interprets it; the
local reducer (`reducer.py`) is its executable specification.
"""

from datetime import datetime

from aviation_events.envelope import Envelope
from aviation_events.reducer import (
    OUTCOME_APPLIED,
    OUTCOME_CONFLICT,
    OUTCOME_DUPLICATE,
    OUTCOME_IGNORED,
    OUTCOME_STORED,
)

# Outcomes the script can report on top of the reducer's.
OUTCOME_REDELIVERED = "redelivered"


def decision_script(project: str, dataset: str) -> str:
    """The single transactional script: decide and write in one round trip.

    Mirrors design section 5 and reducer.py:
    - a committed event_id is a no-write acknowledgement (rule 1);
    - unknown types are recorded and never move state (reducer rule);
    - higher revision replaces the state (rule 3), lower is ignored (4),
      equal payload is a duplicate (5), equal with a different payload is
      a conflict that is receipted, recorded and quarantined (6).

    The conflict reason is built with the same wording as
    ``reducer.decide`` so the dead-letter evidence reads identically.
    """
    return f"""
DECLARE already_seen INT64;
DECLARE outcome STRING;
DECLARE quarantine_reason STRING;
DECLARE current_event_id STRING;
DECLARE current_revision INT64;
DECLARE current_payload STRING;
BEGIN TRANSACTION;
SET already_seen = (
  SELECT COUNT(*) FROM `{project}.{dataset}.event_receipt` WHERE event_id = @event_id
);
IF already_seen > 0 THEN
  SET outcome = '{OUTCOME_REDELIVERED}';
ELSE
  IF NOT @moves_state THEN
    SET outcome = '{OUTCOME_STORED}';
    INSERT `{project}.{dataset}.event_receipt`
      (event_id, message_id, outcome, received_at)
      VALUES (@event_id, @message_id, '{OUTCOME_STORED}', @received_at);
    INSERT `{project}.{dataset}.event_history`
      (event_id, entity_id, revision, outcome, message_id, received_at)
      VALUES (@event_id, @entity_id, @revision, '{OUTCOME_STORED}',
              @message_id, @received_at);
  ELSE
    SET current_event_id = (
      SELECT event_id FROM `{project}.{dataset}.entity_state` WHERE entity_id = @entity_id
    );
    SET current_revision = (
      SELECT revision FROM `{project}.{dataset}.entity_state` WHERE entity_id = @entity_id
    );
    SET current_payload = (
      SELECT payload FROM `{project}.{dataset}.entity_state` WHERE entity_id = @entity_id
    );
    IF current_revision IS NULL OR @revision > current_revision THEN
      SET outcome = '{OUTCOME_APPLIED}';
      INSERT `{project}.{dataset}.event_receipt`
        (event_id, message_id, outcome, received_at)
        VALUES (@event_id, @message_id, '{OUTCOME_APPLIED}', @received_at);
      INSERT `{project}.{dataset}.event_history`
        (event_id, entity_id, revision, outcome, message_id, received_at)
        VALUES (@event_id, @entity_id, @revision, '{OUTCOME_APPLIED}',
                @message_id, @received_at);
      DELETE FROM `{project}.{dataset}.entity_state` WHERE entity_id = @entity_id;
      INSERT `{project}.{dataset}.entity_state`
        (entity_id, revision, event_id, event_type, event_time, payload, updated_at)
        VALUES (@entity_id, @revision, @event_id, @event_type, @event_time,
                @canonical_payload, @received_at);
    ELSEIF @revision < current_revision THEN
      SET outcome = '{OUTCOME_IGNORED}';
      INSERT `{project}.{dataset}.event_receipt`
        (event_id, message_id, outcome, received_at)
        VALUES (@event_id, @message_id, '{OUTCOME_IGNORED}', @received_at);
      INSERT `{project}.{dataset}.event_history`
        (event_id, entity_id, revision, outcome, message_id, received_at)
        VALUES (@event_id, @entity_id, @revision, '{OUTCOME_IGNORED}',
                @message_id, @received_at);
    ELSEIF current_payload = @canonical_payload THEN
      SET outcome = '{OUTCOME_DUPLICATE}';
      INSERT `{project}.{dataset}.event_receipt`
        (event_id, message_id, outcome, received_at)
        VALUES (@event_id, @message_id, '{OUTCOME_DUPLICATE}', @received_at);
      INSERT `{project}.{dataset}.event_history`
        (event_id, entity_id, revision, outcome, message_id, received_at)
        VALUES (@event_id, @entity_id, @revision, '{OUTCOME_DUPLICATE}',
                @message_id, @received_at);
    ELSE
      SET outcome = '{OUTCOME_CONFLICT}';
      SET quarantine_reason = CONCAT(
        'revision ', CAST(@revision AS STRING), ' of ', @entity_id,
        ' already stored with a different payload (stored event ', current_event_id, ')'
      );
      INSERT `{project}.{dataset}.event_receipt`
        (event_id, message_id, outcome, received_at)
        VALUES (@event_id, @message_id, '{OUTCOME_CONFLICT}', @received_at);
      INSERT `{project}.{dataset}.event_history`
        (event_id, entity_id, revision, outcome, message_id, received_at)
        VALUES (@event_id, @entity_id, @revision, '{OUTCOME_CONFLICT}',
                @message_id, @received_at);
      INSERT `{project}.{dataset}.event_quarantine`
        (delivery_key, reason, body, occurrences, first_seen_at, last_seen_at)
        VALUES (@message_id, quarantine_reason, @body, 1, @received_at, @received_at);
    END IF;
  END IF;
END IF;
COMMIT TRANSACTION;
SELECT outcome, IFNULL(quarantine_reason, '') AS reason;
""".strip()


def quarantine_script(project: str, dataset: str) -> str:
    """Upsert for bodies rejected before a decision (missing envelope fields).

    Keyed by delivery and reason, so a redelivered poison message bumps
    ``occurrences`` — the record of repeated failure notifications.
    """
    return f"""
MERGE `{project}.{dataset}.event_quarantine` AS target
USING (SELECT @delivery_key AS delivery_key, @reason AS reason) AS source
ON target.delivery_key = source.delivery_key AND target.reason = source.reason
WHEN MATCHED THEN UPDATE SET
  occurrences = target.occurrences + 1,
  last_seen_at = @seen_at
WHEN NOT MATCHED THEN
  INSERT (delivery_key, reason, body, occurrences, first_seen_at, last_seen_at)
  VALUES (@delivery_key, @reason, @body, 1, @seen_at, @seen_at)
""".strip()


class BigQueryEventStore:
    """Runs the decision script and the quarantine upsert against BigQuery."""

    def __init__(self, dataset: str, *, client=None) -> None:
        self._dataset = dataset
        self._client = client

    def _bigquery(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client()
        return self._client

    def commit_delivery(
        self,
        event: Envelope,
        message_id: str,
        received_at: datetime,
        *,
        moves_state: bool,
        body: bytes,
    ) -> tuple[str, str]:
        """Run the one decision script; returns (outcome, dead-letter reason)."""
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        parameters = [
            ScalarQueryParameter("event_id", "STRING", event.event_id),
            ScalarQueryParameter("entity_id", "STRING", event.entity_id),
            ScalarQueryParameter("event_type", "STRING", event.event_type),
            ScalarQueryParameter("event_time", "TIMESTAMP", event.event_time),
            ScalarQueryParameter("revision", "INT64", event.revision),
            ScalarQueryParameter("canonical_payload", "STRING", event.canonical_payload),
            ScalarQueryParameter("message_id", "STRING", message_id),
            ScalarQueryParameter("received_at", "TIMESTAMP", received_at),
            ScalarQueryParameter("moves_state", "BOOL", moves_state),
            ScalarQueryParameter("body", "STRING", body.decode("utf-8", errors="replace")),
        ]
        job = client.query(
            decision_script(client.project, self._dataset),
            job_config=QueryJobConfig(query_parameters=parameters),
        )
        row = next(iter(job.result()), None)
        if row is None:
            raise OSError("decision script returned no outcome row")
        return (row["outcome"], row["reason"])

    def record_quarantine(
        self, delivery_key: str, reason: str, body: str, seen_at: datetime
    ) -> None:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        client = self._bigquery()
        parameters = [
            ScalarQueryParameter("delivery_key", "STRING", delivery_key),
            ScalarQueryParameter("reason", "STRING", reason),
            ScalarQueryParameter("body", "STRING", body),
            ScalarQueryParameter("seen_at", "TIMESTAMP", seen_at),
        ]
        client.query(
            quarantine_script(client.project, self._dataset),
            job_config=QueryJobConfig(query_parameters=parameters),
        ).result()


class Delivery:
    """One pulled Pub/Sub delivery, mirroring the client's response shape."""

    def __init__(self, ack_id: str, message_id: str, body: bytes, attributes: dict) -> None:
        self.ack_id = ack_id
        self.message_id = message_id
        self.body = body
        self.attributes = attributes


class PubSubPuller:
    """Synchronous pull: the test controls nacks by simply not acking."""

    def __init__(self, subscription: str, *, client=None) -> None:
        self._subscription = subscription
        self._client = client

    def _subscriber(self):
        if self._client is None:
            from google.cloud import pubsub_v1

            self._client = pubsub_v1.SubscriberClient()
        return self._client

    def pull_batch(self, max_messages: int) -> list[Delivery]:
        if max_messages <= 0:
            return []
        response = self._subscriber().pull(
            request={"subscription": self._subscription, "max_messages": max_messages}
        )
        return [
            Delivery(
                ack_id=received.ack_id,
                message_id=received.message.message_id,
                body=received.message.data,
                attributes=dict(received.message.attributes or {}),
            )
            for received in response.received_messages
        ]

    def acknowledge(self, ack_ids: list[str]) -> None:
        if not ack_ids:
            return
        self._subscriber().acknowledge(
            request={"subscription": self._subscription, "ack_ids": ack_ids}
        )

    def nack(self, ack_ids: list[str]) -> None:
        if not ack_ids:
            return
        # Expire the ack deadline so the subscription redelivers at once.
        self._subscriber().modify_ack_deadline(
            request={
                "subscription": self._subscription,
                "ack_ids": ack_ids,
                "ack_deadline_seconds": 0,
            }
        )


class PubSubPublisher:
    """Publishes raw bodies; used by the fixture generator and the replay command."""

    def __init__(self, topic: str, *, client=None) -> None:
        self._topic = topic
        self._client = client

    def _publisher(self):
        if self._client is None:
            from google.cloud import pubsub_v1

            self._client = pubsub_v1.PublisherClient()
        return self._client

    def publish(self, body: bytes, **attributes: str) -> str:
        future = self._publisher().publish(self._topic, body, **attributes)
        return future.result()


class PubSubDeadLetters:
    """DeadLetterSink adapter: attaches the stable reason as a message attribute."""

    def __init__(self, topic: str, *, client=None) -> None:
        self._publisher = PubSubPublisher(topic, client=client)

    def publish(self, body: bytes, reason: str) -> None:
        self._publisher.publish(body, reason=reason)
