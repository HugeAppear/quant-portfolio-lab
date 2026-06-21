"""Event-driven (daily) backtest engine.

Design goals for v0.1: **correctness and transparency**, not speed. The loop
marks the portfolio to the daily close, trades only on rebalance dates, and
delegates every cost calculation to :class:`~quant_portfolio_lab.backtest.
cost_model.CostModel` so the cost logic is never hard-coded in the loop.

Three ways to specify target weights, in priority order:

1. ``targets``     : explicit ``{date: {asset_id: weight}}`` (great for tests).
2. ``target_func`` : ``callable(as_of_date) -> {asset_id: weight}``.
3. factor mode     : rank by PER/PBR over ``fundamentals`` and equal-weight top-N.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..factors.valuation import build_factor_snapshots, rank_by_factor
from ..portfolio.construction import target_weights
from .calendar import generate_rebalance_dates, next_trading_day
from .cost_model import BUY, SELL, CostModel
from .metrics import performance_summary


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    rebalance_mode: str = "1Y"          # "6M" or "1Y"
    top_n: int = 20
    factor: str = "pbr"                 # "per" or "pbr"
    ascending: bool = True              # lowest factor first
    weighting: str = "equal"
    benchmark_id: str | None = None
    periods_per_year: int = 252
    risk_free_rate: float = 0.0
    liquidate_at_end: bool = False      # sell all holdings on the last day


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    positions: pd.DataFrame
    trades: pd.DataFrame
    rebalance_dates: list
    config: BacktestConfig
    benchmark: pd.Series | None = None
    metrics: dict = field(default_factory=dict)
    turnover: float = 0.0

    @property
    def final_value(self) -> float:
        return float(self.equity_curve.iloc[-1]) if len(self.equity_curve) else np.nan

    @property
    def total_return(self) -> float:
        if len(self.equity_curve) < 1:
            return np.nan
        return self.final_value / float(self.equity_curve.iloc[0]) - 1.0


class BacktestEngine:
    def __init__(
        self,
        price_panel: pd.DataFrame,
        cost_model: CostModel | None = None,
        *,
        fundamentals: pd.DataFrame | None = None,
        targets: dict | None = None,
        target_func: Callable | None = None,
        delistings: dict | None = None,
        benchmark: pd.Series | None = None,
        config: BacktestConfig | None = None,
    ) -> None:
        if price_panel.empty:
            raise ValueError("price_panel is empty")

        self.config = config or BacktestConfig()
        self.cost_model = cost_model or CostModel()
        self.fundamentals = fundamentals
        self.explicit_targets = targets
        self.target_func = target_func
        self.benchmark = benchmark

        # Sort, mark on close, forward-fill so held names always have a price.
        panel = price_panel.sort_index()
        panel.index = pd.DatetimeIndex(panel.index)
        self.raw_panel = panel
        self.mark_panel = panel.ffill()
        self.trading_days = panel.index

        # Normalise delisting dates to Timestamps.
        self.delistings = {
            int(a): pd.Timestamp(d) for a, d in (delistings or {}).items()
        }

        self.rebalance_dates = self._resolve_rebalance_dates()

    # ------------------------------------------------------------------ setup
    def _resolve_rebalance_dates(self) -> list[pd.Timestamp]:
        if self.explicit_targets:
            rolled: dict[pd.Timestamp, dict] = {}
            for key, weights in self.explicit_targets.items():
                td = next_trading_day(key, self.trading_days)
                if td is not None:
                    rolled[td] = weights
            self.explicit_targets = rolled
            return sorted(rolled)
        return generate_rebalance_dates(self.trading_days, self.config.rebalance_mode)

    def _targets_for(self, date: pd.Timestamp) -> dict:
        if self.explicit_targets is not None:
            return dict(self.explicit_targets.get(date, {}))
        if self.target_func is not None:
            return dict(self.target_func(date))
        return self._factor_targets(date)

    def _factor_targets(self, date: pd.Timestamp) -> dict:
        if self.fundamentals is None:
            raise ValueError(
                "factor mode requires `fundamentals`; otherwise pass `targets`/`target_func`"
            )
        # Only consider names not yet delisted as of this date.
        live = [a for a in self.mark_panel.columns
                if a not in self.delistings or self.delistings[a] > date]
        snapshots = build_factor_snapshots(
            self.mark_panel[live], self.fundamentals, date
        )
        ranked = rank_by_factor(snapshots, self.config.factor, self.config.ascending)
        return target_weights(ranked, self.config.top_n, self.config.weighting)

    # ------------------------------------------------------------------- loop
    def run(self) -> BacktestResult:
        cfg = self.config
        cash = float(cfg.initial_capital)
        holdings: dict[int, float] = {}
        delisted_done: set[int] = set()

        equity = {}
        position_rows = []
        trade_rows = []
        turnover_acc = []
        last_day = self.trading_days[-1]

        for d in self.trading_days:
            close = self.mark_panel.loc[d]

            # 1) delisting events -> 100% loss (configurable residual).
            for asset_id, del_date in self.delistings.items():
                if asset_id in holdings and asset_id not in delisted_done and d >= del_date:
                    qty = holdings.pop(asset_id)
                    mv = qty * float(close.get(asset_id, 0.0) or 0.0)
                    residual = self.cost_model.apply_delisting(mv)
                    cash += residual
                    delisted_done.add(asset_id)
                    trade_rows.append(self._trade_row(
                        d, asset_id, SELL, qty, 0.0, 0.0, 0.0, 0.0, mv,
                    ))

            # 2) rebalance.
            is_rebalance = d in self.rebalance_dates
            # 3) optional terminal liquidation.
            is_liquidation = cfg.liquidate_at_end and d == last_day

            if is_rebalance or is_liquidation:
                port_value = cash + sum(
                    q * float(close.get(a, 0.0) or 0.0) for a, q in holdings.items()
                )
                if is_liquidation and not is_rebalance:
                    weights = {}  # sell everything
                else:
                    weights = self._targets_for(d)

                target_qty = {}
                for asset_id, w in weights.items():
                    px = float(close.get(asset_id, np.nan))
                    if not np.isfinite(px) or px <= 0:
                        continue
                    target_qty[asset_id] = (w * port_value) / px

                cash, traded_notional = self._rebalance(
                    d, close, holdings, target_qty, cash, trade_rows
                )
                turnover_acc.append(
                    traded_notional / port_value if port_value > 0 else 0.0
                )
                self._record_positions(d, close, holdings, position_rows)

            # 4) mark-to-market equity.
            equity[d] = cash + sum(
                q * float(close.get(a, 0.0) or 0.0) for a, q in holdings.items()
            )

        equity_curve = pd.Series(equity, name="equity").sort_index()
        daily_returns = equity_curve.pct_change().fillna(0.0)
        positions = pd.DataFrame(position_rows)
        trades = pd.DataFrame(trade_rows)

        bench = self._aligned_benchmark(equity_curve.index)
        metrics = performance_summary(
            equity_curve,
            benchmark=bench,
            periods_per_year=cfg.periods_per_year,
            risk_free_rate=cfg.risk_free_rate,
        )
        avg_turnover = float(np.mean(turnover_acc)) if turnover_acc else 0.0
        metrics["avg_turnover"] = avg_turnover

        return BacktestResult(
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            positions=positions,
            trades=trades,
            rebalance_dates=self.rebalance_dates,
            config=cfg,
            benchmark=bench,
            metrics=metrics,
            turnover=avg_turnover,
        )

    # --------------------------------------------------------------- helpers
    def _rebalance(self, d, close, holdings, target_qty, cash, trade_rows):
        """Trade current holdings toward ``target_qty``; return (cash, notional)."""
        assets = set(holdings) | set(target_qty)
        traded_notional = 0.0
        for asset_id in sorted(assets):
            cur = holdings.get(asset_id, 0.0)
            tgt = target_qty.get(asset_id, 0.0)
            delta = tgt - cur
            if abs(delta) < 1e-12:
                continue
            px = float(close.get(asset_id, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            side = BUY if delta > 0 else SELL
            tc = self.cost_model.price_trade(side, abs(delta), px)
            cash += tc.cash_flow
            traded_notional += tc.gross_notional
            trade_rows.append(self._trade_row(
                d, asset_id, side, abs(delta), tc.execution_price,
                tc.gross_notional, tc.commission, tc.transaction_tax,
                tc.slippage_cost,
            ))
            if abs(tgt) < 1e-12:
                holdings.pop(asset_id, None)
            else:
                holdings[asset_id] = tgt
        return cash, traded_notional

    @staticmethod
    def _trade_row(d, asset_id, side, qty, exec_price, gross, commission, tax, slip):
        return {
            "date": pd.Timestamp(d).date(),
            "asset_id": int(asset_id),
            "side": side,
            "quantity": float(qty),
            "execution_price": float(exec_price),
            "gross_notional": float(gross),
            "commission": float(commission),
            "transaction_tax": float(tax),
            "slippage_cost": float(slip),
        }

    @staticmethod
    def _record_positions(d, close, holdings, rows):
        total = sum(q * float(close.get(a, 0.0) or 0.0) for a, q in holdings.items())
        for asset_id, qty in holdings.items():
            mv = qty * float(close.get(asset_id, 0.0) or 0.0)
            rows.append({
                "date": pd.Timestamp(d).date(),
                "asset_id": int(asset_id),
                "weight": (mv / total) if total else 0.0,
                "quantity": float(qty),
                "market_value": float(mv),
            })

    def _aligned_benchmark(self, index) -> pd.Series | None:
        if self.benchmark is None or self.benchmark.empty:
            return None
        bench = self.benchmark.copy()
        bench.index = pd.DatetimeIndex(bench.index)
        return bench.reindex(index).ffill()
