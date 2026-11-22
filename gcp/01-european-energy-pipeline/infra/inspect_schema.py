"""Inspect google_cloud_run_v2_job schema from `terraform providers schema -json`."""

import json
import sys

d = json.load(sys.stdin)
rs = d["provider_schemas"]["registry.terraform.io/hashicorp/google"]["resource_schemas"]
job = rs["google_cloud_run_v2_job"]["block"]
tmpl = job["block_types"]["template"]
print("template nesting:", tmpl.get("nesting_mode"))
print("template sub-blocks:", sorted(tmpl.get("block_types", {}).keys()))
print("template attrs:", sorted(tmpl.get("attributes", {}).keys()))
if "templates" in tmpl.get("block_types", {}):
    inner = tmpl["block_types"]["templates"]
    print("templates nesting:", inner.get("nesting_mode"))
    print("templates sub-blocks:", sorted(inner.get("block_types", {}).keys()))
    print("templates attrs:", sorted(inner.get("attributes", {}).keys()))
