"""G04 · Governed Energy Data Product, local contract phase.

The package implements the release boundary from the [design](../../docs/design.md)
against a store port, so the BigQuery adapter and the Cloud Run publish job
can later be checked against the same fixtures:

- [contract][]   data-product contracts loaded from versioned YAML
- [gate][]       offline quality gate with key-set completeness
- [fixture][]    seeded candidates, including the invalid variants
- [store][]      the product store port, its in-memory fake and role policy
- [publisher][]  publish, retry, withdraw: the release-boundary flow
- [cloud_gcp][]  BigQuery adapters (cloud delivery phase)
"""

from energy_product.contract import DataProductContract, load_contract
from energy_product.gate import GateResult, run_gate
from energy_product.publisher import PublishRequest, publish, withdraw

__all__ = [
    "DataProductContract",
    "GateResult",
    "PublishRequest",
    "load_contract",
    "publish",
    "run_gate",
    "withdraw",
]
