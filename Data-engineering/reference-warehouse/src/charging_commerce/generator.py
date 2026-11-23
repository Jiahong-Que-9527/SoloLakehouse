"""Seeded generator for the European EV Charging & Roaming Commerce workload (E01).

Deterministic under a fixed seed: the same seed, fixture slice, and fault plan
always produce byte-identical payload streams. Faults required by the E01
design (duplicates, 48h late settlements, negative-kWh rows, DST boundaries,
API 429 + mid-pagination crash, schema drift) are injected at frozen indices
so tests and evidence can assert exact counts.
"""

from __future__ import annotations

import json
import random
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from charging_commerce.open_data import fx_rate_on, load_fx_table, load_stations

SEED = 42
N_SESSIONS = 12_000
PAGE_SIZE = 50

SESSION_START = datetime(2025, 10, 1, tzinfo=UTC)
SESSION_END_EXCLUSIVE = datetime(2026, 5, 1, tzinfo=UTC)
# CET/CEST transition nights (UTC instants of the local 03:00/02:00 shifts).
DST_WINDOWS = (
    (datetime(2025, 10, 25, 22, 0, tzinfo=UTC), datetime(2025, 10, 26, 2, 0, tzinfo=UTC)),
    (datetime(2026, 3, 28, 22, 0, tzinfo=UTC), datetime(2026, 3, 29, 2, 0, tzinfo=UTC)),
)

MARKET_WEIGHTS = (("DE", 70), ("CH", 20), ("PL", 10))
CURRENCY_BY_MARKET = {"DE": "EUR", "CH": "CHF", "PL": "PLN"}
FX_PAIR_BY_MARKET = {"DE": None, "CH": "EUR/CHF", "PL": "EUR/PLN"}
ROAMING_PARTNERS = ("HUB-ELVIT-01", "HUB-SWISSCHARGE-02", "HUB-GIREVE-03")

SNAPSHOT_DATES = ("2025-09-15", "2026-01-15", "2026-05-15")  # t0, t1, t2

# (tariff_id, plan_tier, price_per_kwh_eur by t0/t1/t2, roaming_surcharge_eur)
TARIFFS = (
    ("T-DE-STD-01", "standard", ("0.5900", "0.6200", "0.6200"), "0.00"),
    ("T-DE-FAST-01", "fast_dc", ("0.7900", "0.7900", "0.7900"), "0.00"),
    ("T-DE-FLEET-01", "fleet", ("0.4900", "0.4900", "0.4900"), "0.00"),
    ("T-DE-STD-02", "standard", ("0.5700", "0.5700", "0.5700"), "0.00"),
    ("T-ROAM-CH-01", "standard", ("0.5500", "0.5500", "0.5500"), "1.50"),
    ("T-ROAM-PL-01", "standard", ("0.6200", "0.6200", "0.6500"), "0.99"),
)

# Frozen fault plan (E01 decision record; matches docs/design.md §1).
FAULTS = {
    "duplicate_event_fraction": 0.015,
    "late_settlement_fraction": 0.08,
    "late_adjustment_fraction": 0.02,
    "refund_fraction": 0.03,
    "dst_sessions": 40,
    "negative_energy_rows": 25,
    "invalid_timestamp_order_rows": 15,
    "roaming_rate_limit_page": 2,  # 0-based page index, first attempt only
    "roaming_extra_field_index": 500,
    "roaming_missing_currency_index": 1200,
    "roaming_null_pk_index": 2400,
    "roaming_invalid_type_index": 3600,
}

TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _q(value: Decimal | float | str, places: int) -> Decimal:
    """Round half-up to ``places`` decimals (contract §3.3; SQL ROUND semantics)."""
    exp = Decimal(1).scaleb(-places)
    return Decimal(value).quantize(exp, rounding=ROUND_HALF_UP)


def _ts(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(TS_FMT)


@dataclass
class GenerationResult:
    out_dir: Path
    report: dict

    @property
    def sessions_path(self) -> Path:
        return self.out_dir / "charging_sessions.jsonl"

    @property
    def stations_path(self) -> Path:
        return self.out_dir / "stations_snapshots.jsonl"

    @property
    def tariffs_path(self) -> Path:
        return self.out_dir / "tariffs_snapshots.jsonl"

    @property
    def settlements_path(self) -> Path:
        return self.out_dir / "settlements.jsonl"


def generate(out_dir: Path, fixtures_dir: Path, seed: int = SEED) -> GenerationResult:
    """Generate all synthetic payload streams deterministically from the locked fixtures."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    stations = load_stations(fixtures_dir)
    fx_table = load_fx_table(fixtures_dir)

    station_snapshots = _station_snapshots(stations, rng)
    tariff_rows = _tariff_snapshots()
    tariffs_by_market = _tariffs_by_market()
    fx_by_pair = {p: dict(rates) for p, rates in fx_table.items()}

    session_events: list[dict] = []
    settlements: list[dict] = []
    dirty = {"negative_energy_kwh": 0, "invalid_timestamp_order": 0}
    confirmed_gross: dict[str, Decimal] = {
        "EUR": Decimal("0"),
        "CHF": Decimal("0"),
        "PLN": Decimal("0"),
    }
    fee_sums: dict[str, Decimal] = {"CHF": Decimal("0"), "PLN": Decimal("0")}
    dup_rows = adjustments = refunds = dst_sessions = 0
    total_span_s = int((SESSION_END_EXCLUSIVE - SESSION_START).total_seconds())

    for i in range(N_SESSIONS):
        market = rng.choices([m for m, _ in MARKET_WEIGHTS], [w for _, w in MARKET_WEIGHTS])[0]
        currency = CURRENCY_BY_MARKET[market]
        station = stations[rng.randrange(len(stations))]
        market_tariffs = tariffs_by_market[market]
        tariff_id = market_tariffs[rng.randrange(len(market_tariffs))]
        started = SESSION_START + timedelta(seconds=rng.randrange(total_span_s))
        duration_min = rng.randint(15, 180)
        ended = started + timedelta(minutes=duration_min)
        lag = timedelta(minutes=rng.randint(1, 720))
        if rng.random() < FAULTS["late_settlement_fraction"]:
            lag = timedelta(hours=rng.randint(24, 47), minutes=rng.randint(0, 59))
        settled = ended + lag
        power_kw = Decimal(station["nominal_power_kw"] or "0")
        energy = _q(
            max(
                power_kw * Decimal(duration_min) / Decimal(60) * Decimal(rng.uniform(0.3, 1.0)),
                Decimal("1.0"),
            ),
            4,
        )
        rate = (
            Decimal(1)
            if FX_PAIR_BY_MARKET[market] is None
            else Decimal(
                str(fx_rate_on(fx_by_pair, FX_PAIR_BY_MARKET[market], started.strftime("%Y-%m-%d")))
            )
        )
        gross = _q(energy * Decimal(_price_at(tariff_id, started)) * rate, 2)

        session_id = f"S-{market}-{i:06d}"
        event = {
            "session_id": session_id,
            "event_seq": 1,
            "station_id": station["station_id"],
            "tariff_id": tariff_id,
            "country_code": market,
            "currency_code": currency,
            "session_started_at": _ts(started),
            "session_ended_at": _ts(ended),
            "settled_at": _ts(settled),
            "energy_kwh": f"{energy:.4f}",
            "gross_amount_local": f"{gross:.2f}",
            "event_type": "charge",
        }
        session_events.append(event)
        confirmed_gross[currency] += gross

        if rng.random() < FAULTS["duplicate_event_fraction"]:
            session_events.append(dict(event))
            dup_rows += 1
        roll = rng.random()
        if roll < FAULTS["refund_fraction"]:
            refund = dict(event, event_seq=2, event_type="refund")
            refund["gross_amount_local"] = f"{-gross:.2f}"
            refund["settled_at"] = _ts(
                ended + timedelta(hours=rng.randint(24, 47), minutes=rng.randint(0, 59))
            )
            session_events.append(refund)
            # Latest-event semantics: the session's contribution flips from
            # +gross (event 1) to -gross (event 2), i.e. a delta of -2*gross.
            confirmed_gross[currency] -= 2 * gross
            refunds += 1
        elif roll < FAULTS["refund_fraction"] + FAULTS["late_adjustment_fraction"]:
            energy2 = _q(energy * Decimal("0.99"), 4)
            gross2 = _q(energy2 * Decimal(_price_at(tariff_id, started)) * rate, 2)
            adjustment = dict(event, event_seq=2, event_type="late_adjustment")
            adjustment["energy_kwh"] = f"{energy2:.4f}"
            adjustment["gross_amount_local"] = f"{gross2:.2f}"
            adjustment["settled_at"] = _ts(
                ended + timedelta(hours=rng.randint(24, 47), minutes=rng.randint(0, 59))
            )
            session_events.append(adjustment)
            confirmed_gross[currency] += gross2 - gross
            adjustments += 1

        if currency != "EUR":
            partner = ROAMING_PARTNERS[rng.randrange(len(ROAMING_PARTNERS))]
            surcharge = next(Decimal(t[3]) for t in TARIFFS if t[0] == tariff_id)
            fee = _q(surcharge * rate, 2)
            fee_sums[currency] += fee
            settlements.append(
                {
                    "settlement_id": f"RS-{i:06d}",
                    "session_id": session_id,
                    "roaming_partner": partner,
                    "roaming_fee_local": f"{fee:.2f}",
                    "currency_code": currency,
                    "settled_at": _ts(settled + timedelta(minutes=rng.randint(30, 360))),
                }
            )

    # Inject dirty session rows at deterministic positions (quarantined at ingest).
    # Candidates are base event_seq=1 rows without an event_seq=2 follow-up and
    # without duplicates, so a quarantined session removes exactly one raw row
    # and the conservation expectation stays well-defined.
    has_event2 = {row["session_id"] for row in session_events if row["event_seq"] == 2}
    seen_sessions: set[str] = set()
    candidates: list[int] = []
    for idx, row in enumerate(session_events):
        sid = row["session_id"]
        if row["event_seq"] != 1 or sid in has_event2 or sid in seen_sessions:
            continue
        seen_sessions.add(sid)
        candidates.append(idx)
    negative_idx = sorted(rng.sample(candidates, FAULTS["negative_energy_rows"]))
    remaining = [i for i in candidates if i not in set(negative_idx)]
    order_idx = sorted(rng.sample(remaining, FAULTS["invalid_timestamp_order_rows"]))
    for idx in negative_idx:
        row = session_events[idx]
        row["energy_kwh"] = f"{-abs(Decimal(row['energy_kwh'])):.4f}"
        confirmed_gross[row["currency_code"]] -= Decimal(row["gross_amount_local"])
        dirty["negative_energy_kwh"] += 1
    for idx in order_idx:
        row = session_events[idx]
        row["session_started_at"], row["session_ended_at"] = (
            row["session_ended_at"],
            row["session_started_at"],
        )
        confirmed_gross[row["currency_code"]] -= Decimal(row["gross_amount_local"])
        dirty["invalid_timestamp_order"] += 1

    # Force DST-boundary sessions on top of the base stream.
    dst_sessions = 0
    for window in DST_WINDOWS:
        for k in range(FAULTS["dst_sessions"] // 2):
            market = rng.choices([m for m, _ in MARKET_WEIGHTS], [w for _, w in MARKET_WEIGHTS])[0]
            currency = CURRENCY_BY_MARKET[market]
            station = stations[rng.randrange(len(stations))]
            tariff_id = tariffs_by_market[market][rng.randrange(len(tariffs_by_market[market]))]
            started = window[0] + timedelta(minutes=rng.randint(0, 180))
            ended = min(started + timedelta(minutes=rng.randint(30, 210)), window[1])
            settled = ended + timedelta(hours=rng.randint(1, 12))
            session_id = f"S-DST-{window[0]:%Y%m%d}-{k:03d}"
            rate = (
                Decimal(1)
                if FX_PAIR_BY_MARKET[market] is None
                else Decimal(
                    str(
                        fx_rate_on(
                            fx_by_pair, FX_PAIR_BY_MARKET[market], started.strftime("%Y-%m-%d")
                        )
                    )
                )
            )
            price = _price_at(tariff_id, started)
            energy = _q(Decimal(rng.uniform(5, 60)), 4)
            gross = _q(energy * Decimal(price) * rate, 2)
            base = dict(
                session_id=session_id,
                event_seq=1,
                station_id=station["station_id"],
                tariff_id=tariff_id,
            )
            session_events.append(
                dict(
                    base,
                    country_code=market,
                    currency_code=currency,
                    session_started_at=_ts(started),
                    session_ended_at=_ts(ended),
                    settled_at=_ts(settled),
                    energy_kwh=f"{energy:.4f}",
                    gross_amount_local=f"{gross:.2f}",
                    event_type="charge",
                )
            )
            confirmed_gross[currency] += gross
            dst_sessions += 1

    # Inject roaming API fault records at frozen indices (quarantined at ingest).
    faults = FAULTS
    if faults["roaming_extra_field_index"] < len(settlements):
        settlements[faults["roaming_extra_field_index"]] = dict(
            settlements[faults["roaming_extra_field_index"]], legacy_clearing_ref="LEG-2024-007"
        )
    if faults["roaming_missing_currency_index"] < len(settlements):
        settlements[faults["roaming_missing_currency_index"]].pop("currency_code")
    if faults["roaming_null_pk_index"] < len(settlements):
        settlements[faults["roaming_null_pk_index"]]["settlement_id"] = None
    if faults["roaming_invalid_type_index"] < len(settlements):
        settlements[faults["roaming_invalid_type_index"]]["roaming_fee_local"] = "12.5abc"

    _write_jsonl(out_dir / "charging_sessions.jsonl", session_events)
    _write_jsonl(out_dir / "stations_snapshots.jsonl", station_snapshots)
    _write_jsonl(out_dir / "tariffs_snapshots.jsonl", tariff_rows)
    _write_jsonl(out_dir / "settlements.jsonl", settlements)
    (out_dir / "roaming_faults.json").write_text(
        json.dumps({"page_size": PAGE_SIZE, "rate_limit_page": faults["roaming_rate_limit_page"]})
        + "\n"
    )

    report = {
        "seed": seed,
        "stations_fixture_rows": len(stations),
        "raw_expected_rows": {
            "raw_stations_bnetza": len(station_snapshots),
            "raw_tariff_plans": len(tariff_rows),
            "raw_charging_sessions": len(session_events),
            "raw_roaming_settlements": len(settlements),
        },
        "sessions_base": N_SESSIONS,
        "dst_sessions": dst_sessions,
        "duplicate_rows": dup_rows,
        "late_adjustment_events": adjustments,
        "refund_events": refunds,
        "quarantine_expected": {
            "charging_sim": {
                "negative_energy_kwh": dirty["negative_energy_kwh"],
                "invalid_timestamp_order": dirty["invalid_timestamp_order"],
            },
            "roaming_api": {
                "unexpected_schema_drift": 1,
                "missing_required_column": 1,
                "null_primary_key": 1,
                "invalid_type": 1,
            },
        },
        "confirmed_gross_by_currency": {k: f"{v:.2f}" for k, v in confirmed_gross.items()},
        "roaming_fee_by_currency": {k: f"{v:.2f}" for k, v in fee_sums.items()},
    }
    (out_dir / "generation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return GenerationResult(out_dir=out_dir, report=report)


def _price_at(tariff_id: str, moment: datetime) -> str:
    """Tariff list price (EUR/kWh) in force for ``tariff_id`` at UTC ``moment``."""
    for tid, _, prices, _ in TARIFFS:
        if tid == tariff_id:
            for price, start in zip(reversed(prices), reversed(SNAPSHOT_DATES), strict=True):
                if moment.date() >= datetime.fromisoformat(start).date():
                    return price
            return prices[0]
    raise KeyError(tariff_id)


def _tariff_snapshots() -> list[dict]:
    rows = []
    for tid, tier, prices, surcharge in TARIFFS:
        for snapshot, price in zip(SNAPSHOT_DATES, prices, strict=True):
            rows.append(
                {
                    "tariff_id": tid,
                    "snapshot_date": snapshot,
                    "price_per_kwh_eur": price,
                    "roaming_surcharge_eur": surcharge,
                    "plan_tier": tier,
                }
            )
    return rows


def _tariffs_by_market() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {"DE": [], "CH": [], "PL": []}
    for tid, _, _, surcharge in TARIFFS:
        market = "DE" if surcharge == "0.00" else ("CH" if "CH" in tid else "PL")
        mapping[market].append(tid)
    return mapping


def _station_snapshots(stations: list[dict[str, str]], rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    operators = sorted({s["operator_name"] for s in stations if s["operator_name"]})
    t0, t1, t2 = SNAPSHOT_DATES
    for station in stations:
        power = Decimal(station["nominal_power_kw"] or "0")
        roll = rng.random()
        operator_change = rng.random() < 0.02
        predecessor = operators[rng.randrange(len(operators))]
        per_snapshot = {}
        for snapshot in (t0, t1, t2):
            if roll < 0.05:  # upgraded before t1
                per_snapshot[snapshot] = power / 2 if snapshot == t0 else power
            elif roll < 0.10:  # upgraded between t1 and t2
                per_snapshot[snapshot] = power / 2 if snapshot in (t0, t1) else power
            else:
                per_snapshot[snapshot] = power
        for snapshot in SNAPSHOT_DATES:
            rows.append(
                {
                    "station_id": station["station_id"],
                    "snapshot_date": snapshot,
                    "operator_name": predecessor
                    if (operator_change and snapshot == t0)
                    else station["operator_name"],
                    "postal_code": station["postal_code"],
                    "city": station["city"],
                    "federal_state": station["federal_state"],
                    "latitude": station["latitude"],
                    "longitude": station["longitude"],
                    "nominal_power_kw": f"{per_snapshot[snapshot]:g}",
                    "connector_count": station["connector_count"],
                    "commissioned_date": station["commissioned_date"],
                }
            )
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


class MockRoamingServer:
    """In-process paginated roaming API with a frozen fault plan (429 + cursor paging)."""

    def __init__(self, settlements_path: Path, faults_path: Path) -> None:
        self.settlements = [json.loads(line) for line in settlements_path.read_text().splitlines()]
        spec = json.loads(faults_path.read_text())
        self.page_size = spec["page_size"]
        self.rate_limit_page = spec["rate_limit_page"]
        self.rate_limited_pages: set[int] = set()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> str:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib API
                query = parse_qs(urlparse(self.path).query)
                cursor = int(query.get("cursor", ["0"])[0])
                page_index = cursor // server.page_size
                if (
                    page_index == server.rate_limit_page
                    and page_index not in server.rate_limited_pages
                ):
                    server.rate_limited_pages.add(page_index)
                    self.send_error(429, "Too Many Requests")
                    return
                page = server.settlements[cursor : cursor + server.page_size]
                next_cursor = cursor + server.page_size
                body = json.dumps(
                    {
                        "settlements": page,
                        "next_cursor": next_cursor
                        if next_cursor < len(server.settlements)
                        else None,
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:  # silence request logging
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            self._server = None
