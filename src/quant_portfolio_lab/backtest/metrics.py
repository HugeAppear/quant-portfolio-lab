"""Performance metrics for the v0.1 result page.

Provides CAGR, annualised volatility, Sharpe ratio, max drawdown, an annual
return table, and a drawdown series. All functions operate on an equity curve
(a ``pd.Series`` indexed by date).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def to_returns(equity: pd.Series) -> pd.Series:
    return equity.sort_index().pct_change().dropna()


def cagr(equity: pd.Series, periods_per_year: int = 252) -> float:
    equity = equity.sort_index()
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return np.nan
    n_periods = len(equity) - 1
    years = n_periods / periods_per_year
    if years <= 0:
        return np.nan
    return (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0


def excess_cagr(
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """Strategy CAGR minus benchmark CAGR over the aligned date range.
    
    The benchmark is forward-filled onto the strategy equity index so that
    strategy and benchmark are compared over the same dates.
    """
    if strategy_equity is None or benchmark_equity is None:
        return np.nan
    
    strategy = strategy_equity.sort_index().dropna()
    benchmark = benchmark_equity.sort_index().dropna()
    
    if strategy.empty or benchmark.empty:
        return np.nan
    
    aligned = pd.DataFrame(
        {
            "strategy": strategy,
            "benchmark": benchmark.reindex(strategy.index).ffill(),
        }
    ).dropna()
    
    if len(aligned) < 2:
        return np.nan
    
    return cagr(aligned["strategy"], periods_per_year) - cagr(
        aligned["benchmark"],
        periods_per_year
    )


def annualized_volatility(equity: pd.Series, periods_per_year: int = 252) -> float:
    rets = to_returns(equity)
    if rets.empty:
        return np.nan
    return float(rets.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    equity: pd.Series, periods_per_year: int = 252, risk_free_rate: float = 0.0
) -> float:
    rets = to_returns(equity)
    if rets.empty or rets.std(ddof=1) == 0:
        return np.nan
    rf_per_period = risk_free_rate / periods_per_year
    excess = rets - rf_per_period
    return float(excess.mean() / rets.std(ddof=1) * np.sqrt(periods_per_year))


def drawdown_series(equity: pd.Series) -> pd.Series:
    equity = equity.sort_index()
    running_max = equity.cummax()
    return equity / running_max - 1.0


def max_drawdown(equity: pd.Series) -> float:
    dd = drawdown_series(equity)
    return float(dd.min()) if not dd.empty else np.nan


def annual_returns(equity: pd.Series) -> pd.Series:
    """Calendar-year returns derived from the equity curve."""
    equity = equity.sort_index()
    if equity.empty:
        return pd.Series(dtype=float)
    yearly_last = equity.groupby(equity.index.year).last()
    yearly_first = equity.groupby(equity.index.year).first()
    # First year is measured from its own first observation; later years from the
    # previous year-end.
    prev_close = yearly_last.shift(1)
    base = prev_close.copy()
    base.iloc[0] = yearly_first.iloc[0]
    return (yearly_last / base - 1.0).rename("annual_return")


def performance_summary(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> dict:
    """Bundle the headline metrics into a dict for the result page."""
    summary = {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0)
        if len(equity) > 1 else np.nan,
        "cagr": cagr(equity, periods_per_year),
        "volatility": annualized_volatility(equity, periods_per_year),
        "sharpe": sharpe_ratio(equity, periods_per_year, risk_free_rate),
        "max_drawdown": max_drawdown(equity),
        "start": equity.index[0] if len(equity) else None,
        "end": equity.index[-1] if len(equity) else None,
    }
    if benchmark is not None and not benchmark.empty:
        bench = benchmark.reindex(equity.index).ffill().dropna()
        if len(bench) > 1:
            summary["benchmark_total_return"] = float(
                bench.iloc[-1] / bench.iloc[0] - 1.0
            )
            summary["benchmark_cagr"] = cagr(bench, periods_per_year)
            summary["excess_cagr"] = excess_cagr(equity, bench, periods_per_year)
            summary["benchmark_max_drawdown"] = max_drawdown(bench)
    return summary
