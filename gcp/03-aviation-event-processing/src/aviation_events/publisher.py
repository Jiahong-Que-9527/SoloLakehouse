"""Fixture publisher: a test command, not a scheduled producer (design section 6).

Publishes one seeded batch to the events topic from WSL with the owner's
Application Default Credentials. Prints the fixture message id and the
Pub/Sub message id of every delivery so the acceptance evidence can
reconcile inputs to final rows.
"""

import argparse

from aviation_events.generator import airport_batch, energy_batch

BATCHES = {"airport": airport_batch, "energy": energy_batch}


def main(argv: list[str] | None = None) -> int:
    from aviation_events.cloud_gcp import PubSubPublisher

    parser = argparse.ArgumentParser(description="Publish a seeded fixture batch")
    parser.add_argument("--fixture", choices=sorted(BATCHES), required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--project", required=True)
    parser.add_argument("--topic", default="aviation-events")
    args = parser.parse_args(argv)

    topic_path = f"projects/{args.project}/topics/{args.topic}"
    publisher = PubSubPublisher(topic_path)
    for message in BATCHES[args.fixture](args.seed):
        pubsub_id = publisher.publish(message.body)
        print(f"{message.message_id} -> {pubsub_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
