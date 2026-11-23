"""Pure-Python Bronze, Silver, Gold, MERGE, and release-record transforms for D01."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ecb_lakehouse.contracts import ContractError, sha256_file, validate_csv_header

VALID_FREQUENCIES = frozenset({"daily", "irregular"})


@dataclass(frozen=True)
class BronzeRow:
    series_key: str
    observation_date: str
    value: str
    unit: str
    title: str
    source_file: str
    source_batch_id: str
    ingested_at: str


@dataclass(frozen=True)
class SilverRow:
    series_key: str
    observation_date: date
    value: Decimal
    unit: str
    frequency: str
    source_batch_id: str


@dataclass(frozen=True)
class RejectRow:
    series_key: str
    observation_date: str
    value: str
    unit: str
    title: str
    source_file: str
    source_batch_id: str
    reject_reason: str


@dataclass(frozen=True)
class SilverNormalizationResult:
    rows: tuple[SilverRow, ...]
    rejects: tuple[RejectRow, ...]
    duplicate_rows_dropped: int


@dataclass(frozen=True)
class MergeResult:
    rows: tuple[SilverRow, ...]
    inserted: int
    updated: int
    unchanged: int

    @property
    def changed(self) -> bool:
        return self.inserted > 0 or self.updated > 0


@dataclass(frozen=True)
class GoldDailyRow:
    observation_date: date
    usd_per_eur: Decimal
    policy_rate: Decimal
    policy_rate_status: str
    policy_rate_source_date: date
    silver_version: int
    release_id: str


@dataclass(frozen=True)
class MonthlySummaryRow:
    month_utc: str
    last_fx_date: date
    last_usd_per_eur: Decimal
    avg_usd_per_eur: Decimal
    last_policy_rate: Decimal
    observation_days: int


@dataclass(frozen=True)
class ReleaseRecord:
    release_id: str
    source_batch_id: str
    source_hashes: dict[str, str]
    git_sha: str
    silver_fx_table: str
    silver_fx_version: int
    silver_rate_table: str
    silver_rate_version: int
    gold_table: str
    gold_row_count: int
    reject_count: int
    quality_status: str


def load_bronze_csv(path: Path, source_batch_id: str, ingested_at: str) -> list[BronzeRow]:
    """Read an ECB CSV extract into append-only Bronze rows without altering text values."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_csv_header(reader.fieldnames, path)
        rows: list[BronzeRow] = []
        for raw in reader:
            if None in raw:
                raise ContractError(f"{path.name}: unexpected extra column(s) in row {raw!r}")
            rows.append(
                BronzeRow(
                    series_key=raw["series_key"],
                    observation_date=raw["observation_date"],
                    value=raw["value"],
                    unit=raw["unit"],
                    title=raw["title"],
                    source_file=path.name,
                    source_batch_id=source_batch_id,
                    ingested_at=ingested_at,
                )
            )
    return rows


def _parse_iso_date(raw_value: str) -> date | None:
    text = raw_value.strip()
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_decimal(raw_value: str) -> Decimal | None:
    text = raw_value.strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _reject(row: BronzeRow, reason: str) -> RejectRow:
    return RejectRow(
        series_key=row.series_key,
        observation_date=row.observation_date,
        value=row.value,
        unit=row.unit,
        title=row.title,
        source_file=row.source_file,
        source_batch_id=row.source_batch_id,
        reject_reason=reason,
    )


def normalize_silver(
    bronze_rows: Sequence[BronzeRow],
    frequency: str,
) -> SilverNormalizationResult:
    """Validate and deduplicate Bronze rows onto the Silver (series_key, observation_date) grain.

    Identical duplicates within a batch are collapsed to one Silver row. Conflicting duplicates
    for the same key within one batch are rejected together so ambiguous observations never land
    in Silver silently.
    """
    if frequency not in VALID_FREQUENCIES:
        raise ContractError(f"Unsupported frequency {frequency!r}; expected {VALID_FREQUENCIES}")

    rejects: list[RejectRow] = []
    grouped: dict[tuple[str, date], list[tuple[BronzeRow, Decimal, str]]] = defaultdict(list)

    for row in bronze_rows:
        series_key = row.series_key.strip()
        if not series_key:
            rejects.append(_reject(row, "null_series_key"))
            continue

        obs_date = _parse_iso_date(row.observation_date)
        if obs_date is None:
            rejects.append(_reject(row, "invalid_observation_date"))
            continue

        parsed_value = _parse_decimal(row.value)
        if parsed_value is None:
            rejects.append(_reject(row, "non_numeric_value"))
            continue

        unit = row.unit.strip()
        if not unit:
            rejects.append(_reject(row, "null_unit"))
            continue

        grouped[(series_key, obs_date)].append((row, parsed_value, unit))

    silver_rows: list[SilverRow] = []
    duplicate_rows_dropped = 0

    for (series_key, obs_date), entries in sorted(grouped.items()):
        distinct_payloads = {(val, unit) for _, val, unit in entries}
        if len(distinct_payloads) > 1:
            for raw_row, _, _ in entries:
                rejects.append(_reject(raw_row, "conflicting_duplicate_in_batch"))
            continue

        winning_row, winning_value, winning_unit = entries[-1]
        duplicate_rows_dropped += len(entries) - 1
        silver_rows.append(
            SilverRow(
                series_key=series_key,
                observation_date=obs_date,
                value=winning_value,
                unit=winning_unit,
                frequency=frequency,
                source_batch_id=winning_row.source_batch_id,
            )
        )

    return SilverNormalizationResult(
        rows=tuple(silver_rows),
        rejects=tuple(rejects),
        duplicate_rows_dropped=duplicate_rows_dropped,
    )


def merge_silver(existing: Sequence[SilverRow], incoming: Sequence[SilverRow]) -> MergeResult:
    """Merge Silver rows by (series_key, observation_date), keeping unchanged keys intact."""
    table: dict[tuple[str, date], SilverRow] = {
        (row.series_key, row.observation_date): row for row in existing
    }
    inserted = 0
    updated = 0
    unchanged = 0

    for row in incoming:
        key = (row.series_key, row.observation_date)
        current = table.get(key)
        if current is None:
            table[key] = row
            inserted += 1
        elif (
            current.value != row.value
            or current.unit != row.unit
            or current.frequency != row.frequency
        ):
            table[key] = row
            updated += 1
        else:
            unchanged += 1

    ordered = tuple(table[k] for k in sorted(table))
    return MergeResult(rows=ordered, inserted=inserted, updated=updated, unchanged=unchanged)


class VersionedDeltaTable:
    """In-memory versioned Silver table mirroring Delta MERGE + VERSION AS OF semantics."""

    def __init__(self) -> None:
        self._versions: list[tuple[SilverRow, ...]] = [()]

    @property
    def version(self) -> int:
        return len(self._versions) - 1

    @property
    def rows(self) -> tuple[SilverRow, ...]:
        return self._versions[-1]

    def merge(self, incoming: Sequence[SilverRow]) -> MergeResult:
        result = merge_silver(self._versions[-1], incoming)
        if result.changed:
            self._versions.append(result.rows)
        return result

    def version_as_of(self, version: int) -> tuple[SilverRow, ...]:
        if version < 0 or version >= len(self._versions):
            raise ContractError(
                f"Unknown table version {version}; current version is {self.version}"
            )
        return self._versions[version]


def build_gold_daily(
    fx_silver: Sequence[SilverRow],
    rate_silver: Sequence[SilverRow],
    silver_version: int,
    release_id: str,
) -> list[GoldDailyRow]:
    """Derive daily Gold indicators over observed FX dates, labelling carried-forward rates."""
    if not fx_silver:
        raise ContractError("Cannot build Gold without any FX Silver rows.")
    if not rate_silver:
        raise ContractError("Cannot build Gold without any policy-rate Silver rows.")

    ordered_fx = sorted(fx_silver, key=lambda r: r.observation_date)
    ordered_rates = sorted(rate_silver, key=lambda r: r.observation_date)

    gold_rows: list[GoldDailyRow] = []
    rate_idx = 0
    for fx_row in ordered_fx:
        while (
            rate_idx + 1 < len(ordered_rates)
            and ordered_rates[rate_idx + 1].observation_date <= fx_row.observation_date
        ):
            rate_idx += 1

        active_rate = ordered_rates[rate_idx]
        if active_rate.observation_date > fx_row.observation_date:
            iso_day = fx_row.observation_date.isoformat()
            raise ContractError(f"No policy rate available on or before FX date {iso_day}")

        status = (
            "observed"
            if active_rate.observation_date == fx_row.observation_date
            else "carried_forward"
        )
        gold_rows.append(
            GoldDailyRow(
                observation_date=fx_row.observation_date,
                usd_per_eur=fx_row.value,
                policy_rate=active_rate.value,
                policy_rate_status=status,
                policy_rate_source_date=active_rate.observation_date,
                silver_version=silver_version,
                release_id=release_id,
            )
        )

    return gold_rows


def build_gold_monthly_summary(gold_daily: Sequence[GoldDailyRow]) -> list[MonthlySummaryRow]:
    """Aggregate daily Gold indicators by observed calendar month without inventing empty months."""
    by_month: dict[str, list[GoldDailyRow]] = defaultdict(list)
    for row in sorted(gold_daily, key=lambda r: r.observation_date):
        by_month[row.observation_date.strftime("%Y-%m")].append(row)

    summaries: list[MonthlySummaryRow] = []
    for month_utc in sorted(by_month):
        rows = by_month[month_utc]
        last_row = rows[-1]
        avg_fx = (sum((r.usd_per_eur for r in rows), Decimal("0")) / Decimal(len(rows))).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        summaries.append(
            MonthlySummaryRow(
                month_utc=month_utc,
                last_fx_date=last_row.observation_date,
                last_usd_per_eur=last_row.usd_per_eur,
                avg_usd_per_eur=avg_fx,
                last_policy_rate=last_row.policy_rate,
                observation_days=len(rows),
            )
        )
    return summaries


def build_release_record(
    *,
    release_id: str,
    source_batch_id: str,
    source_hashes: dict[str, str],
    git_sha: str,
    silver_fx_table: str,
    silver_fx_version: int,
    silver_rate_table: str,
    silver_rate_version: int,
    gold_table: str,
    gold_row_count: int,
    reject_count: int,
    quality_status: str = "passed",
) -> ReleaseRecord:
    """Create a provenance record tying a Gold release to inputs, versions, rejects, and commit."""
    return ReleaseRecord(
        release_id=release_id,
        source_batch_id=source_batch_id,
        source_hashes=source_hashes,
        git_sha=git_sha,
        silver_fx_table=silver_fx_table,
        silver_fx_version=silver_fx_version,
        silver_rate_table=silver_rate_table,
        silver_rate_version=silver_rate_version,
        gold_table=gold_table,
        gold_row_count=gold_row_count,
        reject_count=reject_count,
        quality_status=quality_status,
    )


def _serialize_silver(rows: Sequence[SilverRow]) -> list[dict[str, str]]:
    return [
        {
            "series_key": row.series_key,
            "observation_date": row.observation_date.isoformat(),
            "value": str(row.value),
            "unit": row.unit,
            "frequency": row.frequency,
            "source_batch_id": row.source_batch_id,
        }
        for row in rows
    ]


def _serialize_gold(rows: Sequence[GoldDailyRow]) -> list[dict[str, Any]]:
    return [
        {
            "observation_date": row.observation_date.isoformat(),
            "usd_per_eur": str(row.usd_per_eur),
            "policy_rate": str(row.policy_rate),
            "policy_rate_status": row.policy_rate_status,
            "policy_rate_source_date": row.policy_rate_source_date.isoformat(),
            "silver_version": row.silver_version,
            "release_id": row.release_id,
        }
        for row in rows
    ]


def _serialize_monthly(rows: Sequence[MonthlySummaryRow]) -> list[dict[str, Any]]:
    return [
        {
            "month_utc": row.month_utc,
            "last_fx_date": row.last_fx_date.isoformat(),
            "last_usd_per_eur": str(row.last_usd_per_eur),
            "avg_usd_per_eur": str(row.avg_usd_per_eur),
            "last_policy_rate": str(row.last_policy_rate),
            "observation_days": row.observation_days,
        }
        for row in rows
    ]


def run_local_rehearsal(fixtures_dir: Path, git_sha: str = "local") -> dict[str, Any]:
    """Execute the full D01 contract, MERGE, time-travel, and Gold flow in pure Python."""
    fx_path = fixtures_dir / "ecb_fx_2025q1.csv"
    rate_path = fixtures_dir / "ecb_policy_rates_2025q1.csv"
    rev_path = fixtures_dir / "ecb_fx_2025q1_revision.csv"

    bronze_fx_init = load_bronze_csv(fx_path, "batch-2025q1-init", "2026-11-23T00:00:00Z")
    bronze_rate_init = load_bronze_csv(rate_path, "batch-2025q1-init", "2026-11-23T00:00:00Z")

    fx_norm = normalize_silver(bronze_fx_init, "daily")
    rate_norm = normalize_silver(bronze_rate_init, "irregular")

    fx_table = VersionedDeltaTable()
    rate_table = VersionedDeltaTable()
    fx_init_merge = fx_table.merge(fx_norm.rows)
    rate_init_merge = rate_table.merge(rate_norm.rows)

    fx_replay_merge = fx_table.merge(fx_norm.rows)
    rate_replay_merge = rate_table.merge(rate_norm.rows)

    gold_v1 = build_gold_daily(fx_table.rows, rate_table.rows, fx_table.version, "d01-2025q1-v1")
    monthly_v1 = build_gold_monthly_summary(gold_v1)

    release_v1 = build_release_record(
        release_id="d01-2025q1-v1",
        source_batch_id="batch-2025q1-init",
        source_hashes={
            fx_path.name: sha256_file(fx_path),
            rate_path.name: sha256_file(rate_path),
        },
        git_sha=git_sha,
        silver_fx_table="silver.clean_fx_rates",
        silver_fx_version=fx_table.version,
        silver_rate_table="silver.clean_interest_rates",
        silver_rate_version=rate_table.version,
        gold_table="gold.daily_euro_indicators",
        gold_row_count=len(gold_v1),
        reject_count=len(fx_norm.rejects) + len(rate_norm.rejects),
    )

    version_before = fx_table.version
    bronze_fx_rev = load_bronze_csv(rev_path, "batch-2025q1-rev1", "2026-11-23T00:05:00Z")
    rev_norm = normalize_silver(bronze_fx_rev, "daily")
    rev_merge = fx_table.merge(rev_norm.rows)
    version_after = fx_table.version
    rev_replay_merge = fx_table.merge(rev_norm.rows)

    gold_v2 = build_gold_daily(fx_table.rows, rate_table.rows, fx_table.version, "d01-2025q1-v2")
    monthly_v2 = build_gold_monthly_summary(gold_v2)

    release_v2 = build_release_record(
        release_id="d01-2025q1-v2",
        source_batch_id="batch-2025q1-rev1",
        source_hashes={
            fx_path.name: sha256_file(fx_path),
            rate_path.name: sha256_file(rate_path),
            rev_path.name: sha256_file(rev_path),
        },
        git_sha=git_sha,
        silver_fx_table="silver.clean_fx_rates",
        silver_fx_version=fx_table.version,
        silver_rate_table="silver.clean_interest_rates",
        silver_rate_version=rate_table.version,
        gold_table="gold.daily_euro_indicators",
        gold_row_count=len(gold_v2),
        reject_count=len(fx_norm.rejects) + len(rate_norm.rejects) + len(rev_norm.rejects),
    )

    before_rows = {
        r["observation_date"]: r for r in _serialize_silver(fx_table.version_as_of(version_before))
    }
    after_rows = {
        r["observation_date"]: r for r in _serialize_silver(fx_table.version_as_of(version_after))
    }

    return {
        "initial": {
            "fx_inserted": fx_init_merge.inserted,
            "rate_inserted": rate_init_merge.inserted,
            "fx_replay_changed": fx_replay_merge.changed,
            "rate_replay_changed": rate_replay_merge.changed,
            "fx_duplicate_drops": fx_norm.duplicate_rows_dropped,
            "rate_duplicate_drops": rate_norm.duplicate_rows_dropped,
            "fx_rejects": [asdict(r) for r in fx_norm.rejects],
            "rate_rejects": [asdict(r) for r in rate_norm.rejects],
            "gold_rows": _serialize_gold(gold_v1),
            "monthly_summary": _serialize_monthly(monthly_v1),
            "release_record": asdict(release_v1),
        },
        "revision": {
            "version_before": version_before,
            "version_after": version_after,
            "merge_inserted": rev_merge.inserted,
            "merge_updated": rev_merge.updated,
            "merge_unchanged": rev_merge.unchanged,
            "revision_replay_changed": rev_replay_merge.changed,
            "before_2025_02_05": before_rows["2025-02-05"],
            "after_2025_02_05": after_rows["2025-02-05"],
            "after_2025_02_06": after_rows["2025-02-06"],
            "gold_rows": _serialize_gold(gold_v2),
            "monthly_summary": _serialize_monthly(monthly_v2),
            "release_record": asdict(release_v2),
        },
    }
