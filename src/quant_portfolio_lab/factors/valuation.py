"""Valuation factors (PER / PBR) with exclusion and point-in-time rules.

Definitions (spec section 4):

    PER = Stock Price / Earnings Per Share
    PBR = Stock Price / Book Value Per Share

Exclusion rules (spec):

    EPS <= 0  -> exclude from low-PER strategy
    BPS <= 0  -> exclude from low-PBR strategy
    EPS or BPS missing -> exclude from factor ranking

Point-in-time rule (prevents look-ahead bias):

    Use only fundamentals with ``report_date <= rebalance_date``.
    Use price as of the rebalance date or the previous trading day.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Default exclusion toggles (mirrors specs/backtest_policy.yaml).
EXCLUDE_EPS_NON_POSITIVE = True
EXCLUDE_BPS_NON_POSITIVE = True


def _as_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def compute_per(price, eps, exclude_non_positive: bool = EXCLUDE_EPS_NON_POSITIVE) -> float:
    """PER = price / EPS. Returns NaN when EPS is missing or (optionally) <= 0."""
    price, eps = _as_float(price), _as_float(eps)
    if np.isnan(price) or np.isnan(eps):
        return np.nan
    if exclude_non_positive and eps <= 0:
        return np.nan
    return price / eps


def compute_pbr(price, bps, exclude_non_positive: bool = EXCLUDE_BPS_NON_POSITIVE) -> float:
    """PBR = price / BPS. Returns NaN when BPS is missing or (optionally) <= 0."""
    price, bps = _as_float(price), _as_float(bps)
    if np.isnan(price) or np.isnan(bps):
        return np.nan
    if exclude_non_positive and bps <= 0:
        return np.nan
    return price / bps


def _price_asof(price_panel: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.Series:
    """Price as of ``as_of_date`` or the most recent prior trading day."""
    as_of_date = pd.Timestamp(as_of_date)
    eligible = price_panel.loc[price_panel.index <= as_of_date]
    if eligible.empty:
        return pd.Series(np.nan, index=price_panel.columns)
    return eligible.iloc[-1]


def _fundamentals_asof(fundamentals: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    """Latest fundamental per asset with ``report_date <= as_of_date``."""
    as_of_date = pd.Timestamp(as_of_date)
    fnd = fundamentals.copy()
    fnd["report_date"] = pd.to_datetime(fnd["report_date"])
    visible = fnd.loc[fnd["report_date"] <= as_of_date]
    if visible.empty:
        return visible.assign(eps=np.nan, bps=np.nan).iloc[0:0]
    visible = visible.sort_values("report_date")
    return visible.groupby("asset_id", as_index=False).last()


def build_factor_snapshots(
    price_panel: pd.DataFrame,
    fundamentals: pd.DataFrame,
    as_of_date,
    *,
    exclude_eps_non_positive: bool = EXCLUDE_EPS_NON_POSITIVE,
    exclude_bps_non_positive: bool = EXCLUDE_BPS_NON_POSITIVE,
) -> pd.DataFrame:
    """Build point-in-time factor snapshots for a single ``as_of_date``.

    Returns one row per asset with columns matching the ``factor_snapshots``
    table: ``asset_id, as_of_date, price, eps, bps, per, pbr,
    valid_for_backtest``.

    ``valid_for_backtest`` is True when a price and both EPS and BPS are
    available point-in-time. The sign exclusions (EPS/BPS <= 0) are reflected by
    NaN in ``per`` / ``pbr`` respectively, so ranking on a factor naturally drops
    non-positive cases.
    """
    as_of_date = pd.Timestamp(as_of_date)
    prices = _price_asof(price_panel, as_of_date)
    fnd = _fundamentals_asof(fundamentals, as_of_date).set_index("asset_id")

    rows = []
    for asset_id in price_panel.columns:
        price = _as_float(prices.get(asset_id, np.nan))
        eps = _as_float(fnd["eps"].get(asset_id, np.nan)) if not fnd.empty else np.nan
        bps = _as_float(fnd["bps"].get(asset_id, np.nan)) if not fnd.empty else np.nan
        per = compute_per(price, eps, exclude_eps_non_positive)
        pbr = compute_pbr(price, bps, exclude_bps_non_positive)
        valid = bool(
            not np.isnan(price) and not np.isnan(eps) and not np.isnan(bps)
        )
        rows.append(
            {
                "asset_id": asset_id,
                "as_of_date": as_of_date.date(),
                "price": price,
                "eps": eps,
                "bps": bps,
                "per": per,
                "pbr": pbr,
                "valid_for_backtest": valid,
            }
        )
    return pd.DataFrame(rows)


def select_universe(factor_df: pd.DataFrame, factor: str = "pbr") -> pd.DataFrame:
    """Keep rows that are valid point-in-time and have a finite factor value."""
    if factor not in {"per", "pbr"}:
        raise ValueError(f"factor must be 'per' or 'pbr', got {factor!r}")
    mask = factor_df["valid_for_backtest"] & factor_df[factor].notna()
    return factor_df.loc[mask].copy()


def rank_by_factor(
    factor_df: pd.DataFrame, factor: str = "pbr", ascending: bool = True
) -> pd.DataFrame:
    """Rank the (already filtered) universe by ``factor`` (lowest first)."""
    ranked = select_universe(factor_df, factor).sort_values(
        factor, ascending=ascending, kind="mergesort"
    )
    ranked = ranked.reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked
