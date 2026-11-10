# Home cluster entrypoint contract

**Status: design only; hardware not provisioned.**

This is the reserved path for the single planned home cluster's eventual Flux entrypoint. Define bootstrap inputs, Git access/decryption, root dependencies and recovery.

No GitRepository/Kustomization object is implemented. The API and bootstrap must work before reconciling resources that depend on Flux itself.

See the [authoritative design](../../../docs/design/v3/architecture.md) and [construction-plan index](../../../docs/design/v3/README.md).
