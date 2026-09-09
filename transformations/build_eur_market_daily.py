"""Build daily EUR-market Gold table from ECB policy, FX panel, and EWG silver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from governance.contracts import contract_path, load_contract
from governance.quality import validate_dataset_quality
from ingestion.iceberg_io import overwrite_table, scan_table
from ingestion.iceberg_schemas import GOLD_EUR_MARKET_DAILY_SCHEMA
from transformations.quality_report import run_silver_quality_report

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog

# Owner-approved L7 FX basket (USD required for EWG restatement).
FX_BASKET_CURRENCIES: tuple[str, ...] = ("USD", "GBP", "CHF", "JPY", "CNY")
_FX_COLUMN_BY_CURRENCY = {
    "USD": "eur_usd",
    "GBP": "eur_gbp",
    "CHF": "eur_chf",
    "JPY": "eur_jpy",
    "CNY": "eur_cny",
}
_GOLD_COLUMNS = [
    "observation_date",
    "ecb_policy_rate_pct",
    "eur_usd",
    "eur_gbp",
    "eur_chf",
    "eur_jpy",
    "eur_cny",
    "eur_usd_return_pct_1d",
    "ewg_close_usd",
    "ewg_close_eur",
    "ewg_return_eur_pct_1d",
    "ewg_price_date",
]


def build_eur_market_daily(
    fx_df: pd.DataFrame,
    ecb_df: pd.DataFrame,
    ewg_df: pd.DataFrame,
    *,
    basket: tuple[str, ...] = FX_BASKET_CURRENCIES,
) -> pd.DataFrame:
    """Build one Gold row per TARGET business day from FX/ECB/EWG silver frames.

    Calendar is unique FX dates. Basket currencies are inner-joined (wide).
    Policy rate and EWG are exact-date lookups with no forward-fill.
    """
    fx = fx_df.copy()
    ecb = ecb_df.copy()
    ewg = ewg_df.copy()

    fx["observation_date"] = pd.to_datetime(fx["observation_date"], errors="coerce").dt.date
    fx["currency"] = fx["currency"].astype(str).str.upper().str.strip()
    fx["fx_rate"] = pd.to_numeric(fx["fx_rate"], errors="coerce")
    fx = fx.dropna(subset=["observation_date", "currency", "fx_rate"])

    basket_upper = tuple(currency.upper() for currency in basket)
    fx_basket = fx[fx["currency"].isin(basket_upper)]
    if fx_basket.empty:
        return pd.DataFrame(columns=_GOLD_COLUMNS)

    pivoted = (
        fx_basket.pivot_table(
            index="observation_date",
            columns="currency",
            values="fx_rate",
            aggfunc="last",
        )
        .rename(columns=_FX_COLUMN_BY_CURRENCY)
        .reset_index()
    )
    required_fx_cols = [_FX_COLUMN_BY_CURRENCY[currency] for currency in basket_upper]
    missing_cols = [column for column in required_fx_cols if column not in pivoted.columns]
    for column in missing_cols:
        pivoted[column] = pd.NA
    # Inner-join semantics: keep only dates where every basket currency published.
    gold = pivoted.dropna(subset=required_fx_cols).copy()
    gold = gold.sort_values("observation_date").reset_index(drop=True)
    gold["eur_usd_return_pct_1d"] = gold["eur_usd"].pct_change(fill_method=None) * 100.0

    ecb["observation_date"] = pd.to_datetime(ecb["observation_date"], errors="coerce").dt.date
    ecb["rate_pct"] = pd.to_numeric(ecb["rate_pct"], errors="coerce")
    ecb = (
        ecb.dropna(subset=["observation_date", "rate_pct"])
        .drop_duplicates(subset=["observation_date"], keep="last")
        .rename(columns={"rate_pct": "ecb_policy_rate_pct"})
    )
    gold = gold.merge(
        ecb[["observation_date", "ecb_policy_rate_pct"]],
        on="observation_date",
        how="left",
    )

    ewg["observation_date"] = pd.to_datetime(ewg["observation_date"], errors="coerce").dt.date
    ewg["close_price"] = pd.to_numeric(ewg["close_price"], errors="coerce")
    ewg = (
        ewg.dropna(subset=["observation_date", "close_price"])
        .drop_duplicates(subset=["observation_date"], keep="last")
        .rename(
            columns={
                "observation_date": "ewg_price_date",
                "close_price": "ewg_close_usd",
            }
        )
    )
    gold = gold.merge(
        ewg[["ewg_price_date", "ewg_close_usd"]],
        left_on="observation_date",
        right_on="ewg_price_date",
        how="left",
    )
    gold["ewg_close_eur"] = gold["ewg_close_usd"] / gold["eur_usd"]
    gold["ewg_return_eur_pct_1d"] = gold["ewg_close_eur"].pct_change(fill_method=None) * 100.0
    # Unmatched equity days keep null ewg_price_date (no forward-fill).
    unmatched = gold["ewg_close_usd"].isna()
    gold.loc[unmatched, "ewg_price_date"] = pd.NaT

    gold = gold.sort_values("observation_date").reset_index(drop=True)
    return gold[_GOLD_COLUMNS]


def run(catalog: "Catalog") -> dict[str, object]:
    """Read silver inputs, build eur_market_daily Gold, write Iceberg, return summary."""
    fx_df = scan_table(catalog, "silver", "ecb_fx_rates_cleaned")
    ecb_df = scan_table(catalog, "silver", "ecb_rates_cleaned")
    ewg_df = scan_table(catalog, "silver", "german_equity_proxy_daily_cleaned")

    if fx_df.empty:
        raise ValueError("No ECB FX silver records found in Iceberg table")

    gold_df = build_eur_market_daily(fx_df, ecb_df, ewg_df)
    run_silver_quality_report(gold_df, "eur_market_daily")
    validate_dataset_quality(
        gold_df,
        load_contract(contract_path("fin.eur_market_daily_gold")),
    )

    overwrite_table(
        catalog,
        "gold",
        "eur_market_daily",
        gold_df,
        GOLD_EUR_MARKET_DAILY_SCHEMA,
    )

    return {"table": "iceberg:gold.eur_market_daily", "row_count": len(gold_df)}
