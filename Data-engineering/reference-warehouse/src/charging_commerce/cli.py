"""Command-line entrypoint: generate, ingest, verify, report (E01).

``refresh-open-data --live`` is an explicit operator action (network + source
websites); ``load-bq`` needs ADC credentials (E06); everything else runs fully
offline. ``audit-dbt`` (E08) parses dbt artifacts into the ops_* tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from charging_commerce import bq_loader, ingestion, observability
from charging_commerce.generator import generate
from charging_commerce.open_data import refresh_open_data, verify_fixtures

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = PACKAGE_ROOT / "fixtures"

DEFAULT_BATCH_IDS = {
    "bnetza": "bnetza-snapshots-0001",
    "tariffs": "tariffs-t0t1t2-0001",
    "sessions": "charging-sim-window-0001",
    "smard": "smard-2025-10-2026-05-0001",
    "ecb": "ecb-2025-09-2026-05-0001",
}


def _payload_path(source: str, data_dir: Path, fixtures_dir: Path) -> Path:
    name = ingestion.SOURCE_PAYLOADS[source]
    generated = source in ingestion.GENERATED_SOURCES
    candidate = Path(data_dir) / "generated" / name if generated else Path(fixtures_dir) / name
    if not candidate.is_file():
        raise SystemExit(
            f"payload not found: {candidate} — run 'charging-commerce generate' first"
            if generated
            else f"locked fixture not found: {candidate}"
        )
    return candidate


def cmd_generate(args: argparse.Namespace) -> int:
    result = generate(Path(args.out_dir), Path(args.fixtures_dir), seed=args.seed)
    print(json.dumps(result.report["raw_expected_rows"], indent=2))
    print(f"generated payloads in {result.out_dir}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    db_path, state_dir = Path(args.db), Path(args.state_dir)
    if args.source == "roaming":
        base_url = args.api_url
        if not base_url:
            raise SystemExit(
                "--api-url is required for the roaming source (start MockRoamingServer first)"
            )
        result = ingestion.ingest_roaming(
            base_url,
            args.batch_id,
            db_path,
            state_dir,
            fail_after_pages=args.fail_after_pages,
        )
    else:
        payload = _payload_path(args.source, Path(args.data_dir), Path(args.fixtures_dir))
        result = ingestion.ingest_file(args.source, payload, args.batch_id, db_path, state_dir)
    status = "skipped (already ingested)" if result.skipped else "ok"
    print(
        f"batch {result.batch_id}: rows_added={result.rows_added} quarantined={result.quarantined} "
        f"pages={result.pages_done} [{status}]"
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    counts = ingestion.raw_counts(db_path)
    reasons = ingestion.quarantine_by_reason(db_path)
    conservation = ingestion.raw_conservation(db_path)
    print("== raw row counts ==")
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")
    print("== quarantine by reject_reason ==")
    for reason, count in sorted(reasons.items()):
        print(f"  {reason}: {count}")
    print("== raw conservation (latest event per session, by currency) ==")
    for currency, total in conservation.items():
        print(f"  {currency}: {total}")
    report_path = Path(args.data_dir) / "generated" / "generation_report.json"
    if report_path.is_file():
        expected = json.loads(report_path.read_text())
        print("== drift vs generation report ==")
        for currency, total in expected["confirmed_gross_by_currency"].items():
            actual = conservation.get(currency, "0.00")
            marker = "OK" if actual == total else "MISMATCH"
            print(f"  {currency}: expected={total} actual={actual} [{marker}]")
        for reasons_expected in expected["quarantine_expected"].values():
            for reason, count in reasons_expected.items():
                actual = reasons.get(reason, 0)
                marker = "OK" if actual == count else "MISMATCH"
                print(f"  quarantine {reason}: expected={count} actual={actual} [{marker}]")
    return 0


def cmd_verify_fixtures(args: argparse.Namespace) -> int:
    counts = verify_fixtures(Path(args.fixtures_dir))
    print("fixture verification OK:")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count} rows")
    return 0


def cmd_refresh_open_data(args: argparse.Namespace) -> int:
    if not args.live:
        raise SystemExit("refusing to hit live sources without --live (explicit operator action)")
    counts = refresh_open_data(Path(args.work_dir), Path(args.fixtures_dir))
    print("refreshed fixtures (not committed automatically):")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count} rows")
    return 0


def cmd_load_bq(args: argparse.Namespace) -> int:
    # Explicit operator action: requires ADC credentials and touches live BigQuery.
    from google.cloud import bigquery

    client = bigquery.Client(project=args.project)
    report = bq_loader.load_raw_to_bigquery(
        client,
        Path(args.fixtures_dir),
        dataset=args.dataset,
        seed=args.seed,
        max_total_bytes=args.max_bytes,
        batch_prefix=args.batch_prefix,
    )
    print(report.summary())
    return 0


def cmd_audit_dbt(args: argparse.Namespace) -> int:
    """Parse dbt artifacts into the ops_* audit tables (E08) and alert on SLO verdicts."""
    exit_code, alerts = observability.audit_dbt_artifacts(
        Path(args.db),
        run_results_path=Path(args.run_results) if args.run_results else None,
        sources_path=Path(args.sources) if args.sources else None,
        warn_hours=args.warn_hours,
        error_hours=args.error_hours,
        git_sha=observability.git_sha_from_env(),
    )
    for alert in alerts:
        print(json.dumps(alert, sort_keys=True))
    summary = (
        f"audit-dbt: exit={exit_code} alerts={len(alerts)} "
        f"(slo warn>{args.warn_hours:g}h error>{args.error_hours:g}h)"
    )
    print(summary)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="charging-commerce", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "generate", help="generate deterministic payload streams from locked fixtures"
    )
    p.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES))
    p.add_argument("--out-dir", default="data/generated")
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("ingest", help="ingest a source into the raw DuckDB layer")
    p.add_argument("source", choices=[*ingestion.SOURCE_PAYLOADS, "roaming"])
    p.add_argument("--batch-id", required=True)
    p.add_argument("--db", default="data/warehouse.duckdb")
    p.add_argument("--state-dir", default="data/state")
    p.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES))
    p.add_argument("--data-dir", default="data")
    p.add_argument(
        "--api-url", default=None, help="base URL of the mock roaming API (roaming source only)"
    )
    p.add_argument(
        "--fail-after-pages", type=int, default=None, help="inject a crash after N pages (drill)"
    )
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("report", help="raw counts, quarantine breakdown and conservation")
    p.add_argument("--db", default="data/warehouse.duckdb")
    p.add_argument("--data-dir", default="data")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verify-fixtures", help="verify locked fixtures against manifest.json")
    p.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES))
    p.set_defaults(func=cmd_verify_fixtures)

    p = sub.add_parser(
        "refresh-open-data", help="re-download open data and rebuild the fixture slice"
    )
    p.add_argument(
        "--live", action="store_true", help="required guard: actually hit the live sources"
    )
    p.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES))
    p.add_argument("--work-dir", default="data/live_refresh")
    p.set_defaults(func=cmd_refresh_open_data)

    p = sub.add_parser(
        "load-bq",
        help="idempotently load the locked raw layer into BigQuery de_raw (E06; needs ADC)",
    )
    p.add_argument("--project", default="slh-gcp-test")
    p.add_argument("--dataset", default="de_raw")
    p.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--max-bytes",
        type=int,
        default=bq_loader.DEFAULT_MAX_TOTAL_BYTES,
        help="upload size guard in bytes (design §2: < 10 MB)",
    )
    p.add_argument("--batch-prefix", default="e06-raw-load")
    p.set_defaults(func=cmd_load_bq)

    p = sub.add_parser(
        "audit-dbt",
        help="parse dbt run_results.json / sources.json into the ops_* audit tables (E08)",
    )
    p.add_argument(
        "--run-results",
        default="dbt_project/target/run_results.json",
        help="dbt run_results.json path (skipped if missing)",
    )
    p.add_argument(
        "--sources",
        default="dbt_project/target/sources.json",
        help="dbt sources.json path (skipped if missing)",
    )
    p.add_argument("--db", default="data/warehouse.duckdb")
    p.add_argument(
        "--warn-hours",
        type=float,
        default=observability.DEFAULT_WARN_HOURS,
        help="freshness SLO warn threshold in hours (contract §1: 24)",
    )
    p.add_argument(
        "--error-hours",
        type=float,
        default=observability.DEFAULT_ERROR_HOURS,
        help="freshness SLO breach threshold in hours (contract §1: 48)",
    )
    p.set_defaults(func=cmd_audit_dbt)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
