"""Silver-to-Gold feature engineering for ECB event impact analysis."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from transformations.quality_report import run_silver_quality_report


def _compute_cumulative_return_pct(returns_pct: pd.Series) -> float:
    gross = (1.0 + (returns_pct / 100.0)).prod()
    return float((gross - 1.0) * 100.0)


def build_gold_features(ecb_df: pd.DataFrame, dax_df: pd.DataFrame) -> pd.DataFrame:
    """Build one feature row per ECB rate-change event."""
    ecb = ecb_df.copy()
    dax = dax_df.copy()

    ecb["observation_date"] = pd.to_datetime(ecb["observation_date"], errors="coerce").dt.date
    ecb["rate_change_bps"] = pd.to_numeric(ecb["rate_change_bps"], errors="coerce")
    ecb["rate_pct"] = pd.to_numeric(ecb["rate_pct"], errors="coerce")

    dax["observation_date"] = pd.to_datetime(dax["observation_date"], errors="coerce").dt.date
    dax["close_price"] = pd.to_numeric(dax["close_price"], errors="coerce")
    dax["daily_return"] = pd.to_numeric(dax["daily_return"], errors="coerce")
    dax = dax.sort_values("observation_date").reset_index(drop=True)

    events = ecb[ecb["rate_change_bps"].fillna(0) != 0].sort_values("observation_date")
    rows: list[dict] = []

    for _, event in events.iterrows():
        event_date = event["observation_date"]
        candidates = dax[
            (dax["observation_date"] >= event_date)
            & (dax["observation_date"] <= (event_date + pd.Timedelta(days=3).to_pytimedelta()))
        ]
        if candidates.empty:
            continue

        event_dax_idx = int(candidates.index[0])
        prev_window = dax.iloc[max(0, event_dax_idx - 5) : event_dax_idx]
        post_window = dax.iloc[event_dax_idx + 1 : event_dax_idx + 6]
        if len(prev_window) < 5 or len(post_window) < 5:
            continue

        dax_pre_close = prev_window.iloc[-1]["close_price"]
        dax_return_1d = dax.iloc[event_dax_idx]["daily_return"]
        dax_return_5d = _compute_cumulative_return_pct(post_window["daily_return"])
        dax_volatility_pre_5d = float(prev_window["daily_return"].std())

        row = {
            "event_date": event_date,
            "rate_change_bps": float(event["rate_change_bps"]),
            "rate_level_pct": float(event["rate_pct"]),
            "is_rate_hike": bool(event["rate_change_bps"] > 0),
            "is_rate_cut": bool(event["rate_change_bps"] < 0),
            "dax_pre_close": float(dax_pre_close),
            "dax_return_1d": float(dax_return_1d),
            "dax_return_5d": float(dax_return_5d),
            "dax_volatility_pre_5d": dax_volatility_pre_5d,
        }
        rows.append(row)

    gold_df = pd.DataFrame(rows)
    if gold_df.empty:
        return gold_df.reindex(
            columns=[
                "event_date",
                "rate_change_bps",
                "rate_level_pct",
                "is_rate_hike",
                "is_rate_cut",
                "dax_pre_close",
                "dax_return_1d",
                "dax_return_5d",
                "dax_volatility_pre_5d",
            ]
        )

    gold_df = gold_df.sort_values("event_date").reset_index(drop=True)
    return gold_df[
        [
            "event_date",
            "rate_change_bps",
            "rate_level_pct",
            "is_rate_hike",
            "is_rate_cut",
            "dax_pre_close",
            "dax_return_1d",
            "dax_return_5d",
            "dax_volatility_pre_5d",
        ]
    ]


def run(minio_client: Any, bucket: str = "sololakehouse") -> str:
    """Read silver ECB/DAX, build gold features, write parquet, and return path."""
    ecb_path = "silver/ecb_rates_cleaned/ecb_rates_cleaned.parquet"
    dax_path = "silver/dax_daily_cleaned/dax_daily_cleaned.parquet"

    ecb_response = minio_client.get_object(bucket, ecb_path)
    try:
        ecb_df = pd.read_parquet(BytesIO(ecb_response.read()))
    finally:
        ecb_response.close()
        ecb_response.release_conn()

    dax_response = minio_client.get_object(bucket, dax_path)
    try:
        dax_df = pd.read_parquet(BytesIO(dax_response.read()))
    finally:
        dax_response.close()
        dax_response.release_conn()

    gold_df = build_gold_features(ecb_df, dax_df)
    run_silver_quality_report(gold_df, "ecb_dax_features")

    gold_path = "gold/rate_impact_features/ecb_dax_features.parquet"
    buffer = BytesIO()
    pq.write_table(
        pa.Table.from_pandas(gold_df, preserve_index=False),
        buffer,
        compression="snappy",
    )
    buffer.seek(0)
    minio_client.put_object(bucket, gold_path, buffer, length=buffer.getbuffer().nbytes)
    return gold_path
