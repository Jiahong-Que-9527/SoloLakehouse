"""Replay command: republish selected dead-lettered bodies to the events topic.

The dead-letter subscription keeps the original body and the reason
attribute (design section 5). Republished bodies keep their original
``event_id``, which is the dedup key — replaying an already applied id
acknowledges without a second write.

Matching deliveries are published and acknowledged; the rest are left
unacknowledged so they stay available for a later selection.
"""

import argparse

from aviation_events.cloud_gcp import PubSubPublisher, PubSubPuller


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay dead-lettered events")
    parser.add_argument("--project", required=True)
    parser.add_argument("--subscription", default="aviation-events-dlq")
    parser.add_argument("--topic", default="aviation-events")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--reason-prefix", default=None, help="only replay matching reasons")
    args = parser.parse_args(argv)

    puller = PubSubPuller(f"projects/{args.project}/subscriptions/{args.subscription}")
    publisher = PubSubPublisher(f"projects/{args.project}/topics/{args.topic}")

    replays = 0
    skipped = 0
    for delivery in puller.pull_batch(args.limit):
        reason = delivery.attributes.get("reason", "")
        if args.reason_prefix is not None and not reason.startswith(args.reason_prefix):
            skipped += 1
            continue
        publisher.publish(delivery.body, replayed_from=delivery.message_id, reason=reason)
        puller.acknowledge([delivery.ack_id])
        replays += 1
        print(f"replayed {delivery.message_id} ({reason or 'no reason attribute'})")
    print(f"replayed={replays} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
