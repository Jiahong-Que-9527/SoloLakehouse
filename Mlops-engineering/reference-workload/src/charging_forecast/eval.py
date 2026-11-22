"""Baselines and the evaluation harness (M03).

Implements the resolved M03 protocol (docs/delivery-plan.md, M03 entry):
rolling-origin monthly folds with a one-day embargo, the MAE/RMSE/sMAPE
metric suite with hour/station/district segments, the seasonal-naive and
per-station median baselines fitted on point-in-time-readable demand only,
and a seeded paired bootstrap for comparing two models on identical folds.

The report renderer emits deterministic bytes: no wall-clock values, sorted
keys, fixed rounding — the same inputs produce the same report bytes, so
committed reports are reproducible from the release ID and parameters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa

from .contract import git_commit, issue_time_utc, sha256_file
from .validation import read_table

US_HOUR = 3_600_000_000
US_DAY = 86_400_000_000
TARGET_HOURS = 24

EMBARGO_DAYS = 1
MIN_TRAIN_ISSUES = 14
MEDIAN_WINDOW_DAYS = 90
BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED = 20261122
REPORT_SCHEMA_VERSION = "charging-eval-report-v1"

WEEKDAYS = 7  # Monday=0 convention, matching the generator's epoch offset


# -- demand access -------------------------------------------------------------


@dataclass
class DemandTable:
    """Per-station realized demand, sorted by hour, with availability stamps."""

    stations: list[str]
    district: dict[str, str]
    hours: dict[str, np.ndarray]
    values: dict[str, np.ndarray]
    avail: dict[str, np.ndarray]


def load_demand(release_dir: Path, cfg: dict) -> DemandTable:
    stations_table = read_table(release_dir, "stations")
    order = np.argsort(np.array(stations_table["station_id"].to_pylist()), kind="stable")
    stations = [stations_table["station_id"][i].as_py() for i in order.tolist()]
    district = {
        stations_table["station_id"][i].as_py(): stations_table["district"][i].as_py()
        for i in order.tolist()
    }

    table = read_table(release_dir, "demand")
    hours_all = table["hour_utc"].cast(pa.int64()).to_numpy()
    vals_all = table["demand_kwh"].to_numpy()
    avail_all = table["available_at"].cast(pa.int64()).to_numpy()

    grouped: dict[str, list[int]] = {}
    for idx, sid in enumerate(table["station_id"].to_pylist()):
        grouped.setdefault(sid, []).append(idx)
    hours, values, avail = {}, {}, {}
    for sid in stations:
        idxs = np.array(grouped[sid])
        sort = np.argsort(hours_all[idxs], kind="stable")
        hours[sid] = hours_all[idxs][sort]
        values[sid] = vals_all[idxs][sort]
        avail[sid] = avail_all[idxs][sort]
    return DemandTable(stations, district, hours, values, avail)


def _value_at(demand: DemandTable, sid: str, hour_us: int, t_us: int) -> float:
    hours, values, avail = demand.hours[sid], demand.values[sid], demand.avail[sid]
    idx = int(np.searchsorted(hours, hour_us))
    if idx < len(hours) and hours[idx] == hour_us and avail[idx] <= t_us:
        return float(values[idx])
    return float("nan")


def issue_time_us(issue_day: date) -> int:
    return int(issue_time_utc(issue_day).timestamp() * 1_000_000)


def target_hours_us(issue_day: date) -> np.ndarray:
    start = datetime.combine(issue_day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    start_us = int(start.timestamp() * 1_000_000)
    return start_us + np.arange(TARGET_HOURS, dtype=np.int64) * US_HOUR


# -- fold plan -------------------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    """One rolling-origin fold: train on issues up to train_last_issue,
    validate on the issue range [issue_start, issue_end]."""

    issue_start: date
    issue_end: date
    train_last_issue: date


def valid_issue_range(cfg: dict) -> tuple[date, date]:
    """Issue days D whose target day D+1 stays inside the release window."""
    start = date.fromisoformat(cfg["window"]["start"][:10])
    end = date.fromisoformat(cfg["window"]["end"][:10]) - timedelta(days=1)
    return start, end


def validate_fold(fold: Fold, first_issue: date, embargo_days: int = EMBARGO_DAYS) -> None:
    """Refuse an embargo violation: the last training issue's target window
    ends at issue + 1 day, and `embargo_days` full days must sit between that
    end and the validation period."""
    if fold.train_last_issue + timedelta(days=1 + embargo_days) > fold.issue_start:
        raise ValueError(
            f"embargo violation: train_last_issue {fold.train_last_issue} targets "
            f"overlap validation starting {fold.issue_start} under embargo {embargo_days}d"
        )
    if fold.issue_end < fold.issue_start or fold.train_last_issue < first_issue:
        raise ValueError(f"degenerate fold: {fold}")


def build_folds(
    cfg: dict, embargo_days: int = EMBARGO_DAYS, min_train_issues: int = MIN_TRAIN_ISSUES
) -> tuple[list[Fold], list[str]]:
    """One fold per calendar month; months with too little training history
    are skipped (returned as the skipped list) so no fold trains on nothing."""
    v_start, v_end = valid_issue_range(cfg)
    folds: list[Fold] = []
    skipped: list[str] = []
    month = date(v_start.year, v_start.month, 1)
    while month <= v_end:
        next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        issue_start = max(month, v_start)
        issue_end = min(next_month - timedelta(days=1), v_end)
        train_last = issue_start - timedelta(days=1 + embargo_days)
        n_train = (train_last - v_start).days + 1
        if n_train < min_train_issues:
            skipped.append(f"{month:%Y-%m}")
        else:
            fold = Fold(issue_start, issue_end, train_last)
            validate_fold(fold, v_start, embargo_days)
            folds.append(fold)
        month = next_month
    return folds, skipped


# -- baselines --------------------------------------------------------------


def seasonal_naive(demand: DemandTable, issue_day: date) -> tuple[np.ndarray, np.ndarray]:
    """Prediction = demand at target hour − 168 h (readable at T); plus labels."""
    t_us = issue_time_us(issue_day)
    targets = target_hours_us(issue_day)
    n_st = len(demand.stations)
    preds = np.full((n_st, TARGET_HOURS), np.nan)
    labels = np.full((n_st, TARGET_HOURS), np.nan)
    for s, sid in enumerate(demand.stations):
        hours, values, avail = demand.hours[sid], demand.values[sid], demand.avail[sid]
        src = targets - 168 * US_HOUR
        idx = np.searchsorted(hours, src)
        idx_clipped = np.minimum(idx, len(hours) - 1)
        hit = (hours[idx_clipped] == src) & (avail[idx_clipped] <= t_us)
        preds[s] = np.where(hit, values[idx_clipped], np.nan)
        lab_idx = np.searchsorted(hours, targets)
        lab_clipped = np.minimum(lab_idx, len(hours) - 1)
        lab_hit = hours[lab_clipped] == targets
        labels[s] = np.where(lab_hit, values[lab_clipped], np.nan)
    return preds, labels


def fit_station_median(
    demand: DemandTable, train_last_issue: date, window_days: int = MEDIAN_WINDOW_DAYS
) -> dict[str, np.ndarray]:
    """Per-station median by (hour of day, weekday) over the trailing window
    of demand readable at the fold's last training issue. 168 cells per
    station; empty cells stay NaN."""
    t_fit = issue_time_us(train_last_issue)
    window_lo = t_fit - window_days * US_DAY
    fitted: dict[str, np.ndarray] = {}
    for sid in demand.stations:
        hours, values, avail = demand.hours[sid], demand.values[sid], demand.avail[sid]
        mask = (hours >= window_lo) & (avail <= t_fit)
        h = hours[mask]
        v = values[mask]
        hod = ((h // US_HOUR) % 24).astype(int)
        dow = ((h // US_DAY) + 3) % WEEKDAYS
        cells = np.full((TARGET_HOURS, WEEKDAYS), np.nan)
        for hour in range(TARGET_HOURS):
            for weekday in range(WEEKDAYS):
                cell = v[(hod == hour) & (dow == weekday)]
                if cell.size:
                    cells[hour, weekday] = float(np.median(cell))
        fitted[sid] = cells
    return fitted


def station_median_predictions(
    demand: DemandTable, fitted: dict[str, np.ndarray], issue_day: date
) -> np.ndarray:
    targets = target_hours_us(issue_day)
    hod = ((targets // US_HOUR) % 24).astype(int)
    dow = (((targets // US_DAY) + 3) % WEEKDAYS).astype(int)
    preds = np.full((len(demand.stations), TARGET_HOURS), np.nan)
    for s, sid in enumerate(demand.stations):
        preds[s] = fitted[sid][hod, dow]
    return preds


def fold_labels(demand: DemandTable, issue_day: date) -> np.ndarray:
    targets = target_hours_us(issue_day)
    labels = np.full((len(demand.stations), TARGET_HOURS), np.nan)
    for s, sid in enumerate(demand.stations):
        hours, values = demand.hours[sid], demand.values[sid]
        idx = np.searchsorted(hours, targets)
        idx_clipped = np.minimum(idx, len(hours) - 1)
        hit = hours[idx_clipped] == targets
        labels[s] = np.where(hit, values[idx_clipped], np.nan)
    return labels


# -- metrics ----------------------------------------------------------------


def _round(x: float) -> float:
    return round(float(x), 6)


def error_metrics(pred: np.ndarray, label: np.ndarray) -> dict:
    finite = np.isfinite(pred) & np.isfinite(label)
    n = int(finite.sum())
    if n == 0:
        return {"n": 0, "excluded": int(pred.size), "mae": None, "rmse": None, "smape": None}
    p, y = pred[finite], label[finite]
    err = p - y
    denom = np.abs(p) + np.abs(y)
    smape_terms = np.where(denom > 0, 2.0 * np.abs(err) / np.where(denom > 0, denom, 1.0), 0.0)
    return {
        "n": n,
        "excluded": int(pred.size - n),
        "mae": _round(np.mean(np.abs(err))),
        "rmse": _round(np.sqrt(np.mean(err**2))),
        "smape": _round(100.0 * np.mean(smape_terms)),
    }


def segment_metrics(
    preds: np.ndarray, labels: np.ndarray, segment: np.ndarray, names: list
) -> dict:
    out = {}
    for name in names:
        mask = segment == name
        out[str(name)] = error_metrics(preds[mask], labels[mask])
    return out


def paired_bootstrap(err_a: np.ndarray, err_b: np.ndarray, seed: int = BOOTSTRAP_SEED) -> dict:
    """Paired comparison of absolute errors: bootstrap the mean of
    |err_a| − |err_b| over identical rows (a worse than b when positive)."""
    finite = np.isfinite(err_a) & np.isfinite(err_b)
    a, b = np.abs(err_a[finite]), np.abs(err_b[finite])
    diff = a - b
    rng = np.random.default_rng(seed)
    n = diff.size
    means = np.empty(BOOTSTRAP_RESAMPLES)
    for i in range(BOOTSTRAP_RESAMPLES):
        idx = rng.integers(0, n, n)
        means[i] = diff[idx].mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "n": n,
        "mean_abs_error_diff": _round(diff.mean()),
        "ci95": [_round(lo), _round(hi)],
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": seed,
        "positive_means_model_a_worse": bool(diff.mean() > 0),
    }


# -- report -----------------------------------------------------------------


def run_baselines(
    release_dir: Path,
    cfg: dict,
    out_dir: Path,
    *,
    embargo_days: int = EMBARGO_DAYS,
    median_window_days: int = MEDIAN_WINDOW_DAYS,
    seed: int = BOOTSTRAP_SEED,
    features_dir: Path | None = None,
) -> dict:
    """Run the fold plan, both baselines and the paired comparison; write
    baseline-report.json and baseline-report.md with deterministic bytes."""
    release_dir, out_dir = Path(release_dir), Path(out_dir)
    demand = load_demand(release_dir, cfg)
    folds, skipped = build_folds(cfg, embargo_days=embargo_days)

    collect = {name: {"pred": [], "label": []} for name in ("seasonal_naive", "station_median")}
    fold_rows = []
    for fold in folds:
        fitted = fit_station_median(demand, fold.train_last_issue, median_window_days)
        issues = (fold.issue_end - fold.issue_start).days + 1
        naive_p, naive_l, med_p = [], [], []
        for offset in range(issues):
            issue_day = fold.issue_start + timedelta(days=offset)
            pred, label = seasonal_naive(demand, issue_day)
            naive_p.append(pred)
            naive_l.append(label)
            med_p.append(station_median_predictions(demand, fitted, issue_day))
        naive_p, naive_l = np.concatenate(naive_p), np.concatenate(naive_l)
        med_p = np.concatenate(med_p)
        collect["seasonal_naive"]["pred"].append(naive_p)
        collect["seasonal_naive"]["label"].append(naive_l)
        collect["station_median"]["pred"].append(med_p)
        collect["station_median"]["label"].append(naive_l)
        fold_rows.append(
            {
                "issue_start": fold.issue_start.isoformat(),
                "issue_end": fold.issue_end.isoformat(),
                "train_last_issue": fold.train_last_issue.isoformat(),
                "issues": issues,
                "rows": int(naive_p.size),
                "mae_seasonal_naive": error_metrics(naive_p, naive_l)["mae"],
                "mae_station_median": error_metrics(med_p, naive_l)["mae"],
            }
        )

    results = {}
    pooled_err: dict[str, np.ndarray] = {}
    n_issues_total = sum((f.issue_end - f.issue_start).days + 1 for f in folds)
    station_arr = np.array(demand.stations)
    district_arr = np.array([demand.district[s] for s in demand.stations])
    for name in ("seasonal_naive", "station_median"):
        pred = np.concatenate(collect[name]["pred"]).ravel()
        label = np.concatenate(collect[name]["label"]).ravel()
        pooled_err[name] = pred - label
        # Row order across the pooled arrays: fold → issue → station → hour.
        hour_seg = np.tile(np.arange(TARGET_HOURS), pred.size // TARGET_HOURS)
        st_seg = np.tile(np.repeat(station_arr, TARGET_HOURS), n_issues_total)
        dist_seg = np.tile(np.repeat(district_arr, TARGET_HOURS), n_issues_total)
        results[name] = {
            "overall": error_metrics(pred, label),
            "by_hour": segment_metrics(pred, label, hour_seg, list(range(TARGET_HOURS))),
            "by_station": segment_metrics(pred, label, st_seg, demand.stations),
            "by_district": segment_metrics(pred, label, dist_seg, sorted(demand.district.values())),
        }

    comparison = paired_bootstrap(
        pooled_err["station_median"], pooled_err["seasonal_naive"], seed=seed
    )

    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    report = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_release_id": manifest["release_id"],
        "source_manifest_sha256": sha256_file(release_dir / "manifest.json"),
        "source_config_sha256": manifest["config_sha256"],
        "source_commit": git_commit(out_dir),
        "fold_plan": {
            "embargo_days": embargo_days,
            "min_train_issues": MIN_TRAIN_ISSUES,
            "folds": fold_rows,
            "skipped_months": skipped,
        },
        "baseline_params": {"median_window_days": median_window_days},
        "results": results,
        "paired_comparison": {
            "model_a": "station_median",
            "model_b": "seasonal_naive",
            **comparison,
        },
    }
    if features_dir is not None:
        fmanifest = json.loads((Path(features_dir) / "manifest.json").read_text(encoding="utf-8"))
        report["feature_release_id"] = fmanifest["feature_release_id"]
        report["feature_manifest_sha256"] = sha256_file(Path(features_dir) / "manifest.json")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "baseline-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "baseline-report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# Baseline report",
        "",
        f"- Source data release: `{report['source_release_id']}` "
        f"(manifest `{report['source_manifest_sha256'][:12]}…`, "
        f"config `{report['source_config_sha256'][:12]}…`).",
        f"- Fold plan: {len(report['fold_plan']['folds'])} monthly folds, embargo "
        f"{report['fold_plan']['embargo_days']} d, min train issues "
        f"{report['fold_plan']['min_train_issues']}, skipped months: "
        f"{', '.join(report['fold_plan']['skipped_months']) or 'none'}.",
        f"- Baselines: seasonal naive (demand at target hour − 168 h) and "
        f"per-station median by (hour, weekday), fitted per fold on a trailing "
        f"{report['baseline_params']['median_window_days']} d window.",
        "",
        "## Per-fold MAE (kWh)",
        "",
        "| Fold | Issues | Rows | Seasonal naive | Station median |",
        "|---|---|---|---|---|",
    ]
    for row in report["fold_plan"]["folds"]:
        lines.append(
            f"| {row['issue_start']} → {row['issue_end']} | {row['issues']} | {row['rows']} "
            f"| {row['mae_seasonal_naive']:.3f} | {row['mae_station_median']:.3f} |"
        )
    lines += [
        "",
        "## Pooled overall metrics",
        "",
        "| Baseline | MAE | RMSE | sMAPE | Rows |",
        "|---|---|---|---|---|",
    ]
    for name, label in (("seasonal_naive", "Seasonal naive"), ("station_median", "Station median")):
        m = report["results"][name]["overall"]
        lines.append(
            f"| {label} | {m['mae']:.3f} | {m['rmse']:.3f} | {m['smape']:.3f} | {m['n']} |"
        )
    pc = report["paired_comparison"]
    lines += [
        "",
        "## Paired comparison (station median vs seasonal naive)",
        "",
        f"Mean absolute-error difference {pc['mean_abs_error_diff']:.4f} kWh "
        f"(positive: median worse), 95% bootstrap CI "
        f"[{pc['ci95'][0]:.4f}, {pc['ci95'][1]:.4f}] over {pc['resamples']} resamples "
        f"(seed {pc['seed']}, n {pc['n']}).",
        "",
        "The numbers in this report are reproducible from the data release ID and the "
        "parameters above; the same inputs render these exact bytes.",
        "",
    ]
    return "\n".join(lines)
