"""Container entrypoint (plan Task 0.1 Step 5 deferred note).

Builds the real app from the Cloud Run environment. Kept in its own module
so importing the contract module (app.py) in tests never constructs the
cloud adapter.
"""

import os

from energy_api.app import create_app
from energy_api.cloud_gcp import GcpQueryLayer
from energy_api.guards import QueryGuard

app = create_app(
    GcpQueryLayer(
        dataset=os.environ.get("BQ_DATASET", "energy_api"),
        view=os.environ.get("BQ_VIEW", "metric_observation"),
        guard=QueryGuard(),
    )
)
