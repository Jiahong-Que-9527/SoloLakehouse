"""Analytics model for the aviation Gold tables (03 M4).

Deploys three reusable views over the ingested Gold tables and verifies
their output against expected results on a fixed sample. Grain and keys:

- ``v_arrival_traffic``   grain: (release_id, day_utc, status)
- ``v_arrival_hourly``    grain: (release_id, day_utc, hour_utc)
- ``v_surface_time``      grain: (release_id, day_utc)

Runway-area activity is deliberately absent: the ``ground_ops`` market
carries no runway evidence (ADR-006 keeps that in future markets), so a
runway view here would fabricate coverage the release does not have.

Every view carries ``release_id``, so results always trace to the release
they came from and multi-release tables stay unambiguous.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

VIEWS = {
    "v_arrival_traffic": """
        SELECT
          release_id, day_utc, status,
          COUNT(*) AS arrivals
        FROM `{project}.{dataset}.ground_ops_arrivals`
        GROUP BY release_id, day_utc, status
    """,
    "v_arrival_hourly": """
        SELECT
          release_id, day_utc,
          EXTRACT(HOUR FROM TIMESTAMP_SECONDS(lastseen_epoch_s)) AS hour_utc,
          COUNT(*) AS arrivals,
          COUNTIF(status = 'labeled') AS labeled_arrivals
        FROM `{project}.{dataset}.ground_ops_arrivals`
        GROUP BY release_id, day_utc, hour_utc
    """,
    "v_surface_time": """
        SELECT
          release_id, day_utc,
          COUNTIF(status = 'labeled') AS labeled_arrivals,
          AVG(IF(status = 'labeled', taxi_in_s, NULL)) / 60 AS taxi_in_min_avg,
          APPROX_QUANTILES(IF(status = 'labeled', taxi_in_s, NULL), 100)
            [OFFSET(50)] / 60 AS taxi_in_min_median,
          MIN(IF(status = 'labeled', taxi_in_s, NULL)) / 60 AS taxi_in_min_min,
          MAX(IF(status = 'labeled', taxi_in_s, NULL)) / 60 AS taxi_in_min_max,
          AVG(IF(status = 'labeled', taxi_path_m, NULL)) AS taxi_path_m_avg,
          COUNTIF(status = 'labeled' AND max_surface_gap_s > 30)
            AS with_gap_over_30s
        FROM `{project}.{dataset}.ground_ops_arrivals`
        GROUP BY release_id, day_utc
    """,
}


class AnalyticsOps:
    """The BigQuery calls the analytics need; faked in tests."""

    def __init__(self, project: str, dataset: str, region: str = "europe-west3"):
        from google.cloud import bigquery
        self.project, self.dataset, self.region = project, dataset, region
        self.client = bigquery.Client(project=project)
        self.job_ids = []

    def sql(self, statement: str) -> list[dict]:
        job = self.client.query(statement)
        self.job_ids.append(job.job_id)
        return [dict(row) for row in job.result()]

    def deploy_views(self) -> None:
        for name, body in VIEWS.items():
            view = f"`{self.project}.{self.dataset}.{name}`"
            self.sql(f"CREATE OR REPLACE VIEW {view} AS "
                     + body.format(project=self.project, dataset=self.dataset))

    def read_view(self, name: str, where: str = "TRUE") -> list[dict]:
        view = f"`{self.project}.{self.dataset}.{name}`"
        return self.sql(f"SELECT * FROM {view} WHERE {where} ORDER BY 1, 2")

    def record_cost(self) -> list[dict]:
        if not self.job_ids:
            return []
        ids = ", ".join(f"'{j}'" for j in self.job_ids)
        rows = self.sql(
            f"SELECT job_id, SUM(total_bytes_processed) AS bytes_processed, "
            f"SUM(total_slot_ms) AS slot_ms "
            f"FROM `region-{self.region}`.INFORMATION_SCHEMA.JOBS "
            f"WHERE job_id IN ({ids}) GROUP BY job_id")
        return rows


def load_expected(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(ops: AnalyticsOps, expected: dict) -> list[dict]:
    """Compare view output on the fixed sample against the expectations."""
    rid = expected["fixed_release_id"]
    results = []

    traffic = ops.read_view("v_arrival_traffic", f"release_id = '{rid}'")
    totals: dict[str, int] = {}
    for row in traffic:
        totals[row["status"]] = totals.get(row["status"], 0) + row["arrivals"]
    for item in expected["v_arrival_traffic"]:
        ok = totals.get(item["status"]) == item["arrivals"]
        results.append({"check": f"traffic.{item['status']}", "expected": item["arrivals"],
                        "actual": totals.get(item["status"]), "passed": ok})

    hourly = ops.read_view("v_arrival_hourly", f"release_id = '{rid}'")
    per_day: dict[str, list[int]] = {}
    for row in hourly:
        day = str(row["day_utc"])
        bucket = per_day.setdefault(day, [0, 0])
        bucket[0] += row["arrivals"]
        bucket[1] += row["labeled_arrivals"]
    for item in expected["v_arrival_hourly"]:
        actual = per_day.get(item["day_utc"], [None, None])
        ok = actual[0] == item["arrivals"] and actual[1] == item["labeled"]
        results.append({"check": f"hourly.{item['day_utc']}",
                        "expected": [item["arrivals"], item["labeled"]],
                        "actual": actual, "passed": ok})

    surface = ops.read_view("v_surface_time", f"release_id = '{rid}'")
    labeled_total = sum(row["labeled_arrivals"] for row in surface)
    exp_surf = expected["v_surface_time"]
    checks = [("labeled_total", labeled_total == exp_surf["labeled_total"]),
              ("days", len(surface) == exp_surf["days"]),
              ("taxi_in_max_within_contract",
               all(row["taxi_in_min_max"] is None
                   or row["taxi_in_min_max"] * 60 <= exp_surf["taxi_in_max_s"]
                   for row in surface)),
              ("taxi_in_positive",
               all(row["taxi_in_min_min"] is None or row["taxi_in_min_min"] > 0
                   for row in surface))]
    for name, ok in checks:
        results.append({"check": f"surface.{name}", "passed": ok})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="aviation")
    parser.add_argument("--region", default="europe-west3")
    parser.add_argument("--expected", type=Path, required=True,
                        help="expected_results.json for the fixed sample")
    parser.add_argument("--skip-deploy", action="store_true",
                        help="verify against existing views only")
    args = parser.parse_args()

    ops = AnalyticsOps(args.project, args.dataset, args.region)
    if not args.skip_deploy:
        ops.deploy_views()
        print(json.dumps({"deployed": sorted(VIEWS)}))
    results = verify(ops, load_expected(args.expected))
    cost = ops.record_cost()
    passed = all(r["passed"] for r in results)
    summary = {
        "status": "passed" if passed else "failed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": results,
        "query_cost": cost,
    }
    print(json.dumps(summary, indent=2, default=str))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
