"""District baselines over the template's fold protocol (M09 domain code).

Baseline definitions stay with the workload; the fold plan, metrics,
paired bootstrap and deterministic report rendering come from the
template's `evaluation` module.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .evaluation import (
    BOOTSTRAP_SEED,
    MEDIAN_WINDOW_DAYS,
    REPORT_SCHEMA_VERSION,
    WEEKDAYS,
    build_folds,
    error_metrics,
    hour_of_day_us,
    paired_bootstrap,
    segment_metrics,
    weekday_of_us,
)
from .features import DistrictDemand
from .releases import US_DAY, git_commit, issue_time_us, sha256_file, target_hours_us

BASELINES = ("district_seasonal_naive", "district_median")


def _load_demand(release_dir: Path) -> DistrictDemand:
    parts = sorted((Path(release_dir) / "data" / "demand").rglob("*.parquet"))
    tables = [pq.read_table(p) for p in parts]
    return DistrictDemand(tables[0] if len(tables) == 1 else pa.concat_tables(tables))


def fit_district_median(
    demand: DistrictDemand, train_last_issue: date, window_days: int = MEDIAN_WINDOW_DAYS
) -> dict[str, np.ndarray]:
    """Per-district median by (hour of day, weekday) over the trailing window
    of demand readable at the fold's last training issue; 168 cells."""
    t_fit = issue_time_us(train_last_issue)
    window_lo = t_fit - window_days * US_DAY
    fitted: dict[str, np.ndarray] = {}
    for district in demand.hours:
        hours, values, avail = (
            demand.hours[district],
            demand.values[district],
            demand.avail[district],
        )
        mask = (hours >= window_lo) & (avail <= t_fit)
        h, v = hours[mask], values[mask]
        hod, dow = hour_of_day_us(h), weekday_of_us(h)
        cells = np.full((24, WEEKDAYS), np.nan)
        for hour in range(24):
            for weekday in range(WEEKDAYS):
                cell = v[(hod == hour) & (dow == weekday)]
                if cell.size:
                    cells[hour, weekday] = float(np.median(cell))
        fitted[district] = cells
    return fitted


def district_median_predictions(
    demand: DistrictDemand, fitted: dict[str, np.ndarray], issue_day: date, districts: list[str]
) -> np.ndarray:
    targets = target_hours_us(issue_day)
    hod, dow = hour_of_day_us(targets), weekday_of_us(targets)
    preds = np.full((len(districts), 24), np.nan)
    for e, district in enumerate(districts):
        preds[e] = fitted[district][hod, dow]
    return preds


def run_baselines(cfg: dict, release_dir: Path, out_dir: Path) -> dict:
    """Run the fold plan and both baselines; write baseline-report.{json,md}
    with deterministic bytes (no wall-clock values)."""
    release_dir, out_dir = Path(release_dir), Path(out_dir)
    demand = _load_demand(release_dir)
    districts = list(cfg["districts"])
    folds, skipped = build_folds(cfg["window"])

    collect = {name: {"pred": [], "label": []} for name in BASELINES}
    fold_rows = []
    for fold in folds:
        fitted = fit_district_median(demand, fold.train_last_issue)
        issues = (fold.issue_end - fold.issue_start).days + 1
        naive_p, naive_l, med_p = [], [], []
        for offset in range(issues):
            issue_day = fold.issue_start + timedelta(days=offset)
            naive_p.append(demand.seasonal_naive(issue_day))
            naive_l.append(demand.labels(issue_day))
            med_p.append(district_median_predictions(demand, fitted, issue_day, districts))
        naive_p, naive_l, med_p = (
            np.concatenate(naive_p),
            np.concatenate(naive_l),
            np.concatenate(med_p),
        )
        collect["district_seasonal_naive"]["pred"].append(naive_p)
        collect["district_seasonal_naive"]["label"].append(naive_l)
        collect["district_median"]["pred"].append(med_p)
        collect["district_median"]["label"].append(naive_l)
        fold_rows.append(
            {
                "issue_start": fold.issue_start.isoformat(),
                "issue_end": fold.issue_end.isoformat(),
                "train_last_issue": fold.train_last_issue.isoformat(),
                "issues": issues,
                "rows": int(naive_p.size),
                "mae_district_seasonal_naive": error_metrics(naive_p, naive_l)["mae"],
                "mae_district_median": error_metrics(med_p, naive_l)["mae"],
            }
        )

    results, pooled_err = {}, {}
    n_issues_total = sum((f.issue_end - f.issue_start).days + 1 for f in folds)
    district_arr = np.array(districts)
    for name in BASELINES:
        pred = np.concatenate(collect[name]["pred"]).ravel()
        label = np.concatenate(collect[name]["label"]).ravel()
        pooled_err[name] = pred - label
        hour_seg = np.tile(np.arange(24), pred.size // 24)
        dist_seg = np.tile(np.repeat(district_arr, 24), n_issues_total)
        results[name] = {
            "overall": error_metrics(pred, label),
            "by_hour": segment_metrics(pred, label, hour_seg, list(range(24))),
            "by_district": segment_metrics(pred, label, dist_seg, districts),
        }

    comparison = paired_bootstrap(
        pooled_err["district_median"], pooled_err["district_seasonal_naive"], seed=BOOTSTRAP_SEED
    )
    report = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "source_release_id": cfg["release_id"],
        "source_manifest_sha256": sha256_file(release_dir / "manifest.json"),
        "source_commit": git_commit(out_dir),
        "fold_plan": {
            "embargo_days": 1,
            "min_train_issues": 14,
            "folds": fold_rows,
            "skipped_months": skipped,
        },
        "baseline_params": {"median_window_days": MEDIAN_WINDOW_DAYS},
        "results": results,
        "paired_comparison": {
            "model_a": "district_median",
            "model_b": "district_seasonal_naive",
            **comparison,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "baseline-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "baseline-report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# District baseline report",
        "",
        f"- Source data release: `{report['source_release_id']}` "
        f"(manifest `{report['source_manifest_sha256'][:12]}…`).",
        f"- Fold plan: {len(report['fold_plan']['folds'])} monthly folds, embargo "
        f"{report['fold_plan']['embargo_days']} d, skipped months: "
        f"{', '.join(report['fold_plan']['skipped_months']) or 'none'}.",
        f"- Baselines: seasonal naive (demand at target hour − 168 h) and "
        f"per-district median by (hour, weekday), fitted per fold on a trailing "
        f"{report['baseline_params']['median_window_days']} d window.",
        "",
        "## Pooled overall metrics",
        "",
        "| Baseline | MAE | RMSE | sMAPE | Rows |",
        "|---|---|---|---|---|",
    ]
    for name, label in (
        ("district_seasonal_naive", "District seasonal naive"),
        ("district_median", "District median"),
    ):
        m = report["results"][name]["overall"]
        lines.append(
            f"| {label} | {m['mae']:.3f} | {m['rmse']:.3f} | {m['smape']:.3f} | {m['n']} |"
        )
    pc = report["paired_comparison"]
    lines += [
        "",
        "## Paired comparison (district median vs seasonal naive)",
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
