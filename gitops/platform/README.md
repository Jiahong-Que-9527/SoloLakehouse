# Platform component ownership

**Status: design only; hardware not provisioned.**

Declare future owners/versions for controllers, CRDs, networking, secrets integration, storage and bounded telemetry. Install dependencies before their consumers.

No CNI, ingress, storage engine or monitoring deployment is performed. Avoid duplicate LoadBalancer controllers and unrestricted deletion of persistent resources.

See the [authoritative design](../../docs/design/v3/delivery-and-environments.md) and [construction-plan index](../../docs/design/v3/README.md).
