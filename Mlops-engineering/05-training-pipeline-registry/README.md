# M05 · Training pipeline, registry and release gate

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** accepted (2026-11-22) · [Roadmap](../README.md) · [ADR-005](../../Frankfurt-Airport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md) · [Acceptance record](evidence/m05-acceptance.md)

Make training a product: one idempotent CLI from validation to registered release, a container image, and a manifest-based release gate with tested rollback.

## Deliverables

- The `pipeline` package: idempotent CLI steps — validate, features, train, evaluate, register, publish — each runnable alone and in sequence.
- A training image built from the locked environment with a pinned base image; CI builds it from this stage onward.
- The MLflow registry layout and the model release manifest per [ADR-005](../../Frankfurt-Airport-adsb-intelligence/docs/adr/ADR-005-cloud-neutral-training-and-model-registry.md): release ID, git SHA, data release ID, metrics, artifact checksum, committed to Git.
- The promotion state machine (candidate → registered → pinned) with the pin consumed by M06, and rollback implemented as re-pinning the previous manifest and re-verifying.

## Acceptance

1. Rerunning the full pipeline over the same inputs changes nothing: idempotence is checked, not claimed.
2. The determinism check passes in CI: two training runs over the same inputs and seed produce identical metrics.
3. A rollback drill re-pins the previous manifest, re-verifies scoring outputs against it and records both version identities per the [evidence guide](../docs/evidence-guide.md).

M06 consumes the pinned release; nothing downstream may read a model that is not pinned by a manifest.
