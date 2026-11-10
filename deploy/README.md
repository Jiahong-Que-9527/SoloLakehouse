# Reusable deployment packaging

**Status: design only; hardware not provisioned.**

Own application packaging independently of VM lifecycle and actual environment values. Existing Dockerfiles and Compose remain under docker/ for compatibility.

Future versioned charts have one source here. GitOps references their release and images. No Chart.yaml or release is provided merely to fill the directory.

See the [authoritative design](../docs/design/v3/delivery-and-environments.md) and [construction-plan index](../docs/design/v3/README.md).
