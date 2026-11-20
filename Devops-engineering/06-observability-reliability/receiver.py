#!/usr/bin/env python3
"""Alertmanager webhook receiver writing alerts to an evidence JSONL file.

Run on the host:  python3 receiver.py evidence/alerts.jsonl
Alertmanager posts to http://host.k3d.internal:9876/alert (k3d injects the
host.k3d.internal name into the cluster's CoreDNS).
"""

import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evidence/alerts.jsonl")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        for alert in payload.get("alerts", []):
            record = {
                "received_at": datetime.now(timezone.utc).isoformat(),
                "status": payload.get("status"),
                "alertname": (alert.get("labels") or {}).get("alertname"),
                "severity": (alert.get("labels") or {}).get("severity"),
                "instance": (alert.get("labels") or {}).get("instance"),
                "summary": (alert.get("annotations") or {}).get("summary"),
                "starts_at": alert.get("startsAt"),
                "ends_at": alert.get("endsAt"),
            }
            with OUT.open("a") as handle:
                handle.write(json.dumps(record) + "\n")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # silence stderr noise
        pass


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    HTTPServer(("0.0.0.0", 9876), Handler).serve_forever()
