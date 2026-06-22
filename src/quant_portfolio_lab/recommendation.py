"""Backtest approval gates and research recommendation tables.

The project policy says this tool is for research and education, not personalized
investment advice. The functions here therefore produce a reproducible research
shortlist from a tested strategy. They do not account for the user's objectives,
risk tolerance, tax situation, liquidity needs, or account constraints.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest.engine import BacktestResult
from .factors.valuation import build_factor_snapshots, rank_by_factor
from .portfolio.construction import target_weights
from .strategies import (
    ADVANCED_STRATEGY_NAMES,
    BASIC_STRATEGIES,
    build_composite_snapshot,
    make_strategy_spec,
    rank_composite_snapshot,
)


@dataclass(frozen=True)
class BacktestApprovalPolicy:
    """Thresholds that decide whether a strategy is good enough to use.

    Leave a field as ``None`` to disable that check. ``max_drawdown`` should be
    negative; for example, ``-0.30`` means the strategy passes only when its max
    drawdown is no worse than -30%.
    """

    min_total_return: float | None = None
    min_cagr: float | None = None
    min_sharpe: float | None = None
    max_drawdown: float | None = None
    min_excess_total_return: float | None = None
    max_avg_turnover: float | None = None


def evaluate_backtest_policy(
    result: BacktestResult,
    policy: BacktestApprovalPolicy,
) -> tuple[bool, pd.DataFrame]:
    """Evaluate ``result`` against ``policy`` and return ``(approved, checks)``."""
    metrics = dict(result.metrics)
    metrics["avg_turnover"] = result.turnover
    if "benchmark_total_return" in metrics:
        metrics["excess_total_return"] = (
            metrics.get("total_return", np.nan) - metrics.get("benchmark_total_return", np.nan)
        )

    checks: list[dict] = []

    def add_check(metric: str, operator: str, threshold: float | None) -> None:
        if threshold is None:
            return
        value = float(metrics.get(metric, np.nan))
        if operator == ">=":
            passed = np.isfinite(value) and value >= threshold
        elif operator == "<=":
            passed = np.isfinite(value) and value <= threshold
        else:  # pragma: no cover - defensive branch
            raise ValueError(f"unknown operator {operator!r}")
        checks.append(
            {
                "metric": metric,
                "value": value,
                "operator": operator,
                "threshold": float(threshold),
                "passed": bool(passed),
            }
        )

    add_check("total_return", ">=", policy.min_total_return)
    add_check("cagr", ">=", policy.min_cagr)
    add_check("sharpe", ">=", policy.min_sharpe)
    # A less severe drawdown is numerically greater: -20% passes a -30% limit.
    add_check("max_drawdown", ">=", policy.max_drawdown)
    add_check("excess_total_return", ">=", policy.min_excess_total_return)
    add_check("avg_turnover", "<=", policy.max_avg_turnover)

    checks_df = pd.DataFrame(checks)
    approved = True if checks_df.empty else bool(checks_df["passed"].all())
    return approved, checks_df


def _as_of_date(price_panel: pd.DataFrame, as_of_date=None) -> pd.Timestamp:
    panel = price_panel.copy()
    panel.index = pd.DatetimeIndex(panel.index)
    if as_of_date is None:
        return pd.Timestamp(panel.sort_index().index[-1])
    requested = pd.Timestamp(as_of_date)
    eligible = panel.sort_index().loc[lambda df: df.index <= requested]
    if eligible.empty:
        raise ValueError(f"no price data on or before as_of_date={requested.date()}")
    return pd.Timestamp(eligible.index[-1])


def _attach_asset_metadata(recs: pd.DataFrame, assets: pd.DataFrame | None) -> pd.DataFrame:
    if assets is None or assets.empty or recs.empty:
        return recs
    wanted = [
        col for col in ["asset_id", "symbol", "name", "market_segment", "exchange", "currency"]
        if col in assets.columns
    ]
    meta = assets[wanted].drop_duplicates("asset_id")
    return recs.merge(meta, on="asset_id", how="left")


def _ordered_columns(df: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "rank",
        "asset_id",
        "symbol",
        "name",
        "target_weight",
        "as_of_date",
        "price",
        "composite_score",
        "pbr",
        "per",
        "momentum_12_1",
        "volatility_252",
        "roe_proxy",
        "market_segment",
        "exchange",
        "currency",
    ]
    cols = [col for col in preferred if col in df.columns]
    remaining = [col for col in df.columns if col not in cols]
    return df[cols + remaining]


def build_recommendation_table(
    strategy: str,
    price_panel: pd.DataFrame,
    fundamentals: pd.DataFrame,
    *,
    assets: pd.DataFrame | None = None,
    as_of_date=None,
    top_n: int = 20,
    weighting: str = "equal",
) -> pd.DataFrame:
    """Build a current research shortlist using a named strategy.

    ``strategy`` may be one of the original valuation strategies (``low_pbr`` or
    ``low_per``) or one of the advanced composite strategies.
    """
    effective_date = _as_of_date(price_panel, as_of_date)

    if strategy in BASIC_STRATEGIES:
        factor = BASIC_STRATEGIES[strategy]
        snapshot = build_factor_snapshots(price_panel, fundamentals, effective_date)
        ranked = rank_by_factor(snapshot, factor=factor, ascending=True)
        weights = target_weights(ranked, top_n=top_n, weighting=weighting)
    elif strategy in ADVANCED_STRATEGY_NAMES:
        spec = make_strategy_spec(strategy, top_n=top_n, weighting=weighting)
        snapshot = build_composite_snapshot(price_panel, fundamentals, effective_date, spec)
        ranked = rank_composite_snapshot(snapshot)
        weights = target_weights(ranked, top_n=top_n, weighting=weighting)
    else:
        raise ValueError(f"unknown strategy {strategy!r}")

    recs = ranked.head(top_n).copy()
    if recs.empty:
        return recs
    recs["target_weight"] = recs["asset_id"].map(weights).fillna(0.0)
    recs["as_of_date"] = effective_date.date()
    recs = _attach_asset_metadata(recs, assets)
    recs = recs.sort_values("rank").reset_index(drop=True)
    return _ordered_columns(recs)


def format_policy_checks(checks: pd.DataFrame) -> str:
    """Human-readable one-line summary for CLI output."""
    if checks.empty:
        return "no approval thresholds were configured"
    parts = []
    for row in checks.to_dict("records"):
        status = "PASS" if row["passed"] else "FAIL"
        parts.append(
            f"{status}: {row['metric']} {row['value']:.4f} "
            f"{row['operator']} {row['threshold']:.4f}"
        )
    return "; ".join(parts)
