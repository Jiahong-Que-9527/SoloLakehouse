# Environment overlay contract

**Status: design only; hardware not provisioned.**

Planned dev, staging and home environments use distinct identities, database/schema/bucket boundaries, quotas and schedules. Most validation environments run on demand.

Do not create empty per-environment directories. Add actual reviewed values when implemented. Logical namespaces share physical capacity/failure domains.

See the [authoritative design](../../../../docs/design/v3/delivery-and-environments.md) and [construction-plan index](../../../../docs/design/v3/README.md).
