# M07 ADR · Push short-lived scoring metrics to a local gateway

**Status** Accepted for the local workload.

Batch scoring and monitoring run as short-lived CLI processes. Prometheus needs
to scrape their latest result after those processes exit. The monitor uses an
HTTP PUT to replace one Pushgateway group, which Prometheus scrapes with
`honor_labels`. One group represents the latest completed monitor invocation.
Signals and the model release are labels. The JSON report retains issue time,
source hashes, observed values, limits and the retraining decision.

Prometheus routes threshold breaches to Alertmanager after a 4-second hold.
The drill uses a 2-second scrape interval, a 2-second evaluation interval and
a 1-second Alertmanager group wait. The webhook must receive a firing alert
within 30 seconds after the shifted report is pushed. A healthy report must
keep Prometheus and the webhook quiet for 10 seconds after its first scrape.
The shipped configuration runs over loopback. It expects one writer to the
gateway group. M08 owns scheduling, run history and retry behavior.

The gateway retains its latest report between runs. A stopped producer can
leave its last result visible, so report presence alone cannot confirm that a
new window was evaluated. The monitor report and gateway write are separate
operations. If publication fails, the CLI exits with an error and the report
remains available for diagnosis and retry.
