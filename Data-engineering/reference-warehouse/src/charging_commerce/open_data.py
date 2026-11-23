"""Open-data fixture handling for E01: locked fixture verification and opt-in live refresh.

The locked fixtures under ``fixtures/`` are the only inputs used by offline CI.
``refresh-open-data --live`` re-downloads the sources and rebuilds the fixture
slice — an explicit operator action, never triggered by tests or CI.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MANIFEST_NAME = "manifest.json"

BNETZA_REGISTER_URL = (
    "https://data.bundesnetzagentur.de/Bundesnetzagentur/DE/Fachthemen/ElektrizitaetundGas/"
    "E-Mobilitaet/Ladesaeulenregister_BNetzA_2026-11-12.xlsx"
)
SMARD_PRICE_URL = "https://api.energy-charts.info/price?bzn=DE-LU&start=1759276800&end=1778457600"
ECB_FX_URL = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
    "?startPeriod=2025-09-01&endPeriod=2026-05-03&format=csvdata"
)

SLICE_KREISE = (
    "Kreisfreie Stadt Frankfurt am Main",
    "Kreisfreie Stadt Wiesbaden",
    "Landkreis Groß-Gerau",
    "Landkreis Main-Kinzig-Kreis",
)

FX_PAIRS = {"CHF": "EUR/CHF", "PLN": "EUR/PLN", "USD": "EUR/USD"}

# Browser-like headers: the BNetzA CDN rejects default clients (observed 404 with curl UA).
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / MANIFEST_NAME).read_text(encoding="utf-8"))


class FixtureVerificationError(RuntimeError):
    """Raised when a locked fixture fails its manifest checksum or row count."""


def verify_fixtures(fixtures_dir: Path) -> dict[str, int]:
    """Verify every locked fixture against ``manifest.json`` SHA-256 digests.

    Returns the row counts per fixture. Raises ``FixtureVerificationError`` on
    any checksum mismatch — offline CI must never run against tampered inputs.
    """
    manifest = load_manifest(fixtures_dir)
    counts: dict[str, int] = {}
    for name, entry in manifest["fixtures"].items():
        path = fixtures_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"locked fixture missing: {path}")
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise FixtureVerificationError(
                f"fixture checksum mismatch for {name}: manifest={entry['sha256'][:12]}… "
                f"actual={actual[:12]}…"
            )
        with path.open(newline="", encoding="utf-8") as f:
            counts[name] = sum(1 for _ in csv.DictReader(f))
        if counts[name] != entry["row_count"]:
            raise FixtureVerificationError(
                f"fixture row count mismatch for {name}: manifest={entry['row_count']} "
                f"actual={counts[name]}"
            )
    return counts


def load_fx_table(fixtures_dir: Path) -> dict[str, dict[str, float]]:
    """Load ``ecb_fx_slice.csv`` as ``{pair: {date: rate}}`` (ECB base notation)."""
    table: dict[str, dict[str, float]] = {}
    with (fixtures_dir / "ecb_fx_slice.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table.setdefault(row["currency_pair"], {})[row["observation_date"]] = float(row["rate"])
    return table


def fx_rate_on(table: dict[str, dict[str, float]], pair: str, day: str) -> float:
    """Latest ECB rate with ``observation_date <= day`` (carry-forward, never lookahead)."""
    rates = table.get(pair)
    if not rates:
        raise KeyError(f"currency pair not in fixture: {pair}")
    best = max((d for d in rates if d <= day), default=None)
    if best is None:
        raise KeyError(f"no ECB observation on or before {day} for {pair}")
    return rates[best]


def load_stations(fixtures_dir: Path) -> list[dict[str, str]]:
    """Load the locked BNetzA slice as the station pool (t2 attributes)."""
    with (fixtures_dir / "bnetza_hesse_slice.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# Live refresh (explicit operator action only)
# --------------------------------------------------------------------------


def _download(url: str, dest: Path) -> None:
    import urllib.request

    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=300) as resp, dest.open("wb") as out:  # noqa: S310
        while chunk := resp.read(1 << 20):
            out.write(chunk)


def _parse_register_slice(xlsx_path: Path) -> list[dict[str, str]]:
    """Extract the Rhein-Main slice from the BNetzA register XLSX (stdlib only)."""
    z = zipfile.ZipFile(xlsx_path)
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shared = [
        "".join(t.text or "" for t in si.iter(f"{m}t"))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
    ]
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def col(ref: str) -> str:
        return re.match(r"([A-Z]+)", ref).group(1)

    def cellval(c: ET.Element) -> str:
        v = c.find(f"{m}v")
        if v is None:
            return ""
        return shared[int(v.text)] if c.get("t") == "s" else v.text

    epoch = dt.date(1899, 12, 30)
    rows: list[dict[str, str]] = []
    for r in sheet.iter(f"{m}row"):
        if int(r.get("r")) < 12:  # 10 preamble rows + header on row 11
            continue
        cells = {col(c.get("r")): cellval(c) for c in r.findall(f"{m}c")}
        if cells.get("O") != "Hessen" or cells.get("N") not in SLICE_KREISE:
            continue
        commissioned = ""
        if cells.get("H", "").strip():
            commissioned = (epoch + dt.timedelta(days=int(float(cells["H"])))).isoformat()
        power = float(cells.get("G", "0").replace(",", ".") or 0)
        rows.append(
            {
                "station_id": cells.get("A", "").strip(),
                "operator_name": cells.get("B", "").strip(),
                "status": cells.get("D", "").strip(),
                "connector_count": cells.get("F", "").strip(),
                "nominal_power_kw": f"{power:g}",
                "commissioned_date": commissioned,
                "postal_code": cells.get("L", "").strip(),
                "city": cells.get("M", "").strip(),
                "kreis": cells.get("N", "").strip(),
                "federal_state": cells.get("O", "").strip(),
                "latitude": cells.get("P", "").strip().replace(",", "."),
                "longitude": cells.get("Q", "").strip().replace(",", "."),
            }
        )
    rows.sort(key=lambda d: int(d["station_id"]))
    return rows


def refresh_open_data(work_dir: Path, fixtures_dir: Path) -> dict:
    """Re-download sources into ``work_dir`` and rebuild the locked fixture slice.

    Writes the same three fixture CSVs plus an updated ``manifest.json`` with
    fresh SHA-256 digests and retrieval dates. Caller decides whether to commit
    the refreshed slice; this function never runs inside tests or CI.
    """
    import urllib.request

    raw_dir = work_dir / "downloads"
    raw_dir.mkdir(parents=True, exist_ok=True)

    bnetza_path = raw_dir / "ladesaeulenregister.xlsx"
    request = urllib.request.Request(BNETZA_REGISTER_URL, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=600) as resp, bnetza_path.open("wb") as out:  # noqa: S310
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    station_rows = _parse_register_slice(bnetza_path)

    smard_path = raw_dir / "price_de_lu.json"
    _download(SMARD_PRICE_URL, smard_path)
    price_doc = json.loads(smard_path.read_text())

    ecb_dir = raw_dir / "ecb"
    ecb_dir.mkdir(exist_ok=True)
    ecb_rows: list[dict[str, str]] = []
    for currency, pair in FX_PAIRS.items():
        dest = ecb_dir / f"fx_{currency}.csv"
        _download(ECB_FX_URL.format(currency=currency), dest)
        with dest.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ecb_rows.append(
                    {
                        "currency_pair": pair,
                        "observation_date": row["TIME_PERIOD"],
                        "rate": f"{float(row['OBS_VALUE']):.6f}",
                    }
                )
    ecb_rows.sort(key=lambda x: (x["currency_pair"], x["observation_date"]))

    # SMARD prices: 15-minute DE-LU day-ahead, null slots dropped (documented in manifest).
    window_start = dt.datetime(2025, 10, 1, tzinfo=dt.UTC)
    window_end = dt.datetime(2026, 5, 11, tzinfo=dt.UTC)
    price_rows: list[dict[str, str]] = []
    dropped_null = 0
    for ts, price in zip(price_doc["unix_seconds"], price_doc["price"], strict=True):
        if price is None:
            dropped_null += 1
            continue
        moment = dt.datetime.fromtimestamp(ts, dt.UTC)
        if not (window_start <= moment <= window_end):
            continue
        price_rows.append(
            {
                "timestamp_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "market_zone": "DE-LU",
                "wholesale_eur_mwh": f"{price:.4f}",
                "grid_load_mwh": "",
            }
        )
    price_rows.sort(key=lambda x: x["timestamp_utc"])

    fixtures_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "bnetza_hesse_slice.csv": (station_rows, list(station_rows[0].keys())),
        "smard_prices_slice.csv": (
            price_rows,
            ["timestamp_utc", "market_zone", "wholesale_eur_mwh", "grid_load_mwh"],
        ),
        "ecb_fx_slice.csv": (ecb_rows, ["currency_pair", "observation_date", "rate"]),
    }
    manifest_entries: dict[str, dict] = {}
    for name, (data, fieldnames) in outputs.items():
        path = fixtures_dir / name
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
        manifest_entries[name] = {"row_count": len(data), "sha256": sha256_file(path)}

    manifest = {
        "manifest_version": 1,
        "locked_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fixtures": {
            "bnetza_hesse_slice.csv": {
                "source": "Bundesnetzagentur Ladesäulenregister",
                "source_url": BNETZA_REGISTER_URL,
                "license": "CC BY 4.0",
                "retrieval_date": dt.date.today().isoformat(),
                "extraction": (
                    "Rows with Bundesland='Hessen' and Kreis in "
                    + repr(SLICE_KREISE)
                    + "; Excel serial dates converted to ISO; comma decimals normalized. "
                    "This real slice is the t2 station attributes; t0/t1 states are seeded "
                    "synthetic history (generator.py)."
                ),
                **manifest_entries["bnetza_hesse_slice.csv"],
            },
            "smard_prices_slice.csv": {
                "source": (
                    "Bundesnetzagentur SMARD market data (via Fraunhofer ISE energy-charts API)"
                ),
                "source_url": SMARD_PRICE_URL,
                "license": (
                    "CC BY 4.0 (creativecommons.org/licenses/by/4.0) "
                    "from Bundesnetzagentur | SMARD.de"
                ),
                "retrieval_date": dt.date.today().isoformat(),
                "extraction": (
                    "DE-LU day-ahead prices, 15-minute resolution, UTC window "
                    "2025-10-01T00:00Z..2026-05-11T00:00Z; null-price slots dropped; "
                    "grid_load_mwh carried as an empty column "
                    "(endpoint does not provide a load series)."
                ),
                "dropped_null_prices": dropped_null,
                **manifest_entries["smard_prices_slice.csv"],
            },
            "ecb_fx_slice.csv": {
                "source": "ECB Data Portal reference exchange rates",
                "source_url": ECB_FX_URL.format(currency="{CHF,PLN,USD}"),
                "license": "ECB Data Portal terms of use (ECB reference rates, public)",
                "retrieval_date": dt.date.today().isoformat(),
                "extraction": (
                    "Daily reference rates in ECB base notation: rate = foreign currency units "
                    "per 1 EUR; business days only (weekends/TARGET2 holidays absent)."
                ),
                **manifest_entries["ecb_fx_slice.csv"],
            },
        },
    }
    (fixtures_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {name: entry["row_count"] for name, entry in manifest_entries.items()}
