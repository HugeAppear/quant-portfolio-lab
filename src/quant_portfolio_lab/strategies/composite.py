"""Advanced point-in-time strategy signals.

This module adds reusable multi-factor strategy definitions without changing the
backtest engine. The engine already supports ``target_func(as_of_date)``; each
strategy below simply turns point-in-time data into target weights.

All signals use data available on or before ``as_of_date``:

- valuation: PER/PBR from point-in-time fundamentals and current price
- momentum: 12-month return skipping the most recent month by default
- low volatility: annualized realized volatility through ``as_of_date``
- quality: a simple ROE proxy, ``eps / bps``, because v0.1 fundamentals expose
  EPS and BPS but not full financial statement line items
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

from ..factors.valuation import build_factor_snapshots
from ..portfolio.construction import target_weights

BASIC_STRATEGIES: dict[str, str] = {
    "low_pbr": "pbr",
    "low_per": "per",
}

DEFAULT_ADVANCED_STRATEGIES: dict[str, dict[str, float]] = {
    # Balanced value + trend + profitability signal.
    "value_momentum_quality": {
        "value": 0.45,
        "momentum": 0.35,
        "quality": 0.20,
    },
    # More conservative profile: cheap stocks with lower realized volatility.
    "defensive_value": {
        "value": 0.45,
        "low_vol": 0.40,
        "quality": 0.15,
    },
    # Useful when fundamentals are sparse or stale but prices are available.
    "momentum_lowvol": {
        "momentum": 0.55,
        "low_vol": 0.45,
    },
}

ADVANCED_STRATEGY_NAMES = tuple(DEFAULT_ADVANCED_STRATEGIES)
ALL_STRATEGY_NAMES = tuple(BASIC_STRATEGIES) + ADVANCED_STRATEGY_NAMES


@dataclass(frozen=True)
class CompositeStrategySpec:
    """Configuration for an advanced composite strategy."""

    name: str = "value_momentum_quality"
    factor_weights: Mapping[str, float] = field(
        default_factory=lambda: DEFAULT_ADVANCED_STRATEGIES["value_momentum_quality"]
    )
    top_n: int = 20
    weighting: str = "equal"
    momentum_lookback: int = 252
    momentum_skip: int = 21
    volatility_lookback: int = 252
    min_price_history: int = 126

    def normalized_factor_weights(self) -> dict[str, float]:
        clean = {}
        for key, value in self.factor_weights.items():
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if np.isfinite(value) and value > 0:
                clean[str(key)] = value
        total = sum(clean.values())
        if total <= 0:
            raise ValueError("at least one positive factor weight is required")
        return {key: value / total for key, value in clean.items()}


def make_strategy_spec(
    name: str,
    *,
    top_n: int = 20,
    weighting: str = "equal",
    factor_weights: Mapping[str, float] | None = None,
    momentum_lookback: int = 252,
    momentum_skip: int = 21,
    volatility_lookback: int = 252,
    min_price_history: int = 126,
) -> CompositeStrategySpec:
    """Build a named advanced strategy specification."""
    if factor_weights is None:
        if name not in DEFAULT_ADVANCED_STRATEGIES:
            raise ValueError(
                f"unknown advanced strategy {name!r}; choose one of {ADVANCED_STRATEGY_NAMES}"
            )
        factor_weights = DEFAULT_ADVANCED_STRATEGIES[name]
    return CompositeStrategySpec(
        name=name,
        factor_weights=dict(factor_weights),
        top_n=top_n,
        weighting=weighting,
        momentum_lookback=momentum_lookback,
        momentum_skip=momentum_skip,
        volatility_lookback=volatility_lookback,
        min_price_history=min_price_history,
    )


def _price_history(price_panel: pd.DataFrame, as_of_date) -> pd.DataFrame:
    as_of_date = pd.Timestamp(as_of_date)
    history = price_panel.copy()
    history.index = pd.DatetimeIndex(history.index)
    return history.sort_index().loc[lambda df: df.index <= as_of_date].ffill()


def _higher_is_better_score(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if clean.notna().sum() == 0:
        return pd.Series(np.nan, index=series.index)
    return clean.rank(pct=True, ascending=True, method="average")


def _lower_is_better_score(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if clean.notna().sum() == 0:
        return pd.Series(np.nan, index=series.index)
    return clean.rank(pct=True, ascending=False, method="average")


def momentum_12_1(
    price_panel: pd.DataFrame,
    as_of_date,
    *,
    lookback: int = 252,
    skip: int = 21,
) -> pd.Series:
    """Return trailing 12-1 style momentum for every asset.

    The default signal is ``P(t - 1 month) / P(t - 12 months) - 1``. If the
    history is too short, the function returns NaN for every asset.
    """
    history = _price_history(price_panel, as_of_date)
    if len(history) <= max(lookback, skip + 1):
        return pd.Series(np.nan, index=price_panel.columns, name="momentum_12_1")
    recent = history.iloc[-skip - 1]
    past = history.iloc[-lookback]
    out = recent / past - 1.0
    out = out.replace([np.inf, -np.inf], np.nan)
    return out.rename("momentum_12_1")


def realized_volatility(
    price_panel: pd.DataFrame,
    as_of_date,
    *,
    lookback: int = 252,
    min_history: int = 126,
    periods_per_year: int = 252,
) -> pd.Series:
    """Annualized realized volatility through ``as_of_date``."""
    history = _price_history(price_panel, as_of_date)
    returns = history.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    if len(returns) < min_history:
        return pd.Series(np.nan, index=price_panel.columns, name="volatility_252")
    window = returns.tail(lookback)
    vol = window.std(ddof=1) * np.sqrt(periods_per_year)
    return vol.rename("volatility_252")


def build_composite_snapshot(
    price_panel: pd.DataFrame,
    fundamentals: pd.DataFrame,
    as_of_date,
    spec: CompositeStrategySpec | None = None,
) -> pd.DataFrame:
    """Build a point-in-time signal table for a composite strategy."""
    spec = spec or make_strategy_spec("value_momentum_quality")
    base = build_factor_snapshots(price_panel, fundamentals, as_of_date).copy()
    base = base.set_index("asset_id", drop=False)

    mom = momentum_12_1(
        price_panel,
        as_of_date,
        lookback=spec.momentum_lookback,
        skip=spec.momentum_skip,
    )
    vol = realized_volatility(
        price_panel,
        as_of_date,
        lookback=spec.volatility_lookback,
        min_history=spec.min_price_history,
    )
    base["momentum_12_1"] = mom.reindex(base.index).to_numpy()
    base["volatility_252"] = vol.reindex(base.index).to_numpy()

    eps = pd.to_numeric(base["eps"], errors="coerce")
    bps = pd.to_numeric(base["bps"], errors="coerce")
    base["roe_proxy"] = (eps / bps).where(bps > 0).replace([np.inf, -np.inf], np.nan)

    # Component scores are percentiles in [0, 1], where larger is always better.
    base["pbr_score"] = _lower_is_better_score(base["pbr"])
    base["per_score"] = _lower_is_better_score(base["per"])
    base["value_score"] = base[["pbr_score", "per_score"]].mean(axis=1, skipna=True)
    base["momentum_score"] = _higher_is_better_score(base["momentum_12_1"])
    base["low_vol_score"] = _lower_is_better_score(base["volatility_252"])
    base["quality_score"] = _higher_is_better_score(base["roe_proxy"])

    score_cols = {
        "value": "value_score",
        "momentum": "momentum_score",
        "low_vol": "low_vol_score",
        "quality": "quality_score",
    }
    weights = spec.normalized_factor_weights()
    composite = pd.Series(0.0, index=base.index, dtype=float)
    required_cols = []
    for factor_name, weight in weights.items():
        if factor_name not in score_cols:
            raise ValueError(
                f"unknown factor component {factor_name!r}; choose from {tuple(score_cols)}"
            )
        col = score_cols[factor_name]
        required_cols.append(col)
        composite = composite + weight * pd.to_numeric(base[col], errors="coerce")

    base["composite_score"] = composite.replace([np.inf, -np.inf], np.nan)
    base["valid_for_strategy"] = base[required_cols].notna().all(axis=1)
    base["strategy_name"] = spec.name
    return base.reset_index(drop=True)


def rank_composite_snapshot(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Rank valid composite-signal rows, best first."""
    if snapshot.empty:
        return snapshot.copy()
    ranked = snapshot.loc[
        snapshot["valid_for_strategy"] & snapshot["composite_score"].notna()
    ].copy()
    ranked = ranked.sort_values(
        ["composite_score", "asset_id"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked


def weights_for_date(
    price_panel: pd.DataFrame,
    fundamentals: pd.DataFrame,
    as_of_date,
    spec: CompositeStrategySpec,
) -> dict:
    """Return target weights for ``spec`` at ``as_of_date``."""
    snapshot = build_composite_snapshot(price_panel, fundamentals, as_of_date, spec)
    ranked = rank_composite_snapshot(snapshot)
    return target_weights(ranked, spec.top_n, spec.weighting)
