"""Backtesting: rebalance calendar, cost model, engine, and metrics."""

from .calendar import generate_rebalance_dates, next_trading_day
from .cost_model import CostModel, SlippageTier, TradeCost
from .engine import BacktestConfig, BacktestEngine, BacktestResult
from .metrics import excess_cagr, performance_summary

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "CostModel",
    "SlippageTier",
    "TradeCost",
    "generate_rebalance_dates",
    "next_trading_day",
    "performance_summary",
    "excess_cagr",
]
