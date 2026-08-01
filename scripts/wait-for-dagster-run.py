#!/usr/bin/env python3
"""Poll Dagster until the newest run for one job reaches a terminal status."""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

TERMINAL_STATUSES = {"SUCCESS", "FAILURE", "CANCELED"}


def _graphql(url: str, query: str, variables: dict[str, object]) -> dict[str, object]:
    response = requests.post(
        url,
        json={"query": query, "variables": variables},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GraphQL response missing data")
    return data


def latest_run_for_job(base_url: str, job_name: str) -> tuple[str, str]:
    data = _graphql(
        f"{base_url.rstrip('/')}/graphql",
        """
        query LatestRun($pipelineName: String!) {
          runsOrError(filter: { pipelineName: $pipelineName }, limit: 1) {
            ... on Runs {
              results { runId status }
            }
          }
        }
        """,
        {"pipelineName": job_name},
    )
    runs_or_error = data["runsOrError"]
    if not isinstance(runs_or_error, dict):
        raise RuntimeError("GraphQL runsOrError must be an object")
    runs = runs_or_error.get("results")
    if not isinstance(runs, list) or not runs:
        raise RuntimeError(f"no runs found for job {job_name!r}")
    run = runs[0]
    if not isinstance(run, dict):
        raise RuntimeError("GraphQL run entry must be an object")
    return str(run["runId"]), str(run["status"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    base_url = os.environ.get("DAGSTER_URL", "http://localhost:3000")
    deadline = time.monotonic() + args.timeout_seconds
    while time.monotonic() < deadline:
        run_id, status = latest_run_for_job(base_url, args.job)
        if status in TERMINAL_STATUSES:
            if status != "SUCCESS":
                message = f"Dagster run {run_id} for {args.job!r} finished with {status}"
                print(message, file=sys.stderr)
                return 1
            print(run_id)
            return 0
        time.sleep(args.poll_seconds)

    print(f"timed out waiting for {args.job!r} to finish", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
