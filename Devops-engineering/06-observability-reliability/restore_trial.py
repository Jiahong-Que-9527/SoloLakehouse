#!/usr/bin/env python3
"""Restore the trial configmap from the fixture file and verify."""
import hashlib
import json
import subprocess
import sys

NS = "energy-quality-trial"
CM = "energy-quality-audit-report"
FIXTURE = "/home/bill/src/SoloLakehouse/Devops-engineering/reference-service/fixtures/report-passed.json"

raw = open(FIXTURE).read()
patch = json.dumps({"data": {"report-passed.json": raw}})
subprocess.run(
    ["kubectl", "-n", NS, "patch", "cm", CM, "--type", "merge", "-p", patch],
    check=True, capture_output=True,
)
print("configmap patched from fixture file")
subprocess.run(
    ["kubectl", "-n", NS, "rollout", "restart", "deploy/energy-quality"],
    check=True, capture_output=True,
)
r = subprocess.run(
    ["kubectl", "-n", NS, "rollout", "status", "deploy/energy-quality", "--timeout=120s"],
    capture_output=True, text=True,
)
print("rollout:", (r.stdout or r.stderr).strip())

h = lambda s: hashlib.sha256(json.dumps(json.loads(s), sort_keys=True).encode()).hexdigest()[:16]
cm = subprocess.run(
    ["kubectl", "-n", NS, "get", "cm", CM, "-o", "jsonpath={.data.report-passed\\.json}"],
    capture_output=True, text=True,
).stdout
print("semantic checksum configmap:", h(cm), "| fixture:", h(raw), "| match:", h(cm) == h(raw))
