"""Backtest engine validation (Step 9, Tests 1-4) plus calendar checks."""

import numpy as np
import pandas as pd
import pytest

from quant_portfolio_lab.backtest.calendar import (
    generate_rebalance_dates,
    next_trading_day,
)
from quant_portfolio_lab.backtest.cost_model import CostModel
from quant_portfolio_lab.backtest.engine import BacktestConfig, BacktestEngine

CAPITAL = 1_000_000.0


def _one_asset_panel(n=260, seed=1, start_price=10_000.0):
    dates = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0004, 0.01, size=n)
    close = start_price * np.exp(np.cumsum(rets))
    return pd.DataFrame({1: close}, index=dates)


# --------------------------------------------------------------------------- #
# Step 9 -- Test 1: one asset, no costs, buy and hold == asset return
# --------------------------------------------------------------------------- #
def test_buy_and_hold_equals_asset_return():
    panel = _one_asset_panel()
    first = panel.index[0]
    engine = BacktestEngine(
        panel,
        CostModel(0.0, 0.0, 0.0),
        targets={first: {1: 1.0}},
        config=BacktestConfig(initial_capital=CAPITAL),
    )
    result = engine.run()

    asset_return = panel[1].iloc[-1] / panel[1].iloc[0] - 1.0
    assert result.total_return == pytest.approx(asset_return, rel=1e-9)
    # No frictional costs were charged.
    assert result.trades["commission"].sum() == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Step 9 -- Test 2: fees reduce the final value by exactly the commissions
# --------------------------------------------------------------------------- #
def test_fees_reduce_final_value_correctly():
    panel = _one_asset_panel()
    first = panel.index[0]
    p0, pN = panel[1].iloc[0], panel[1].iloc[-1]

    common = dict(targets={first: {1: 1.0}},
                  config=BacktestConfig(initial_capital=CAPITAL, liquidate_at_end=True))

    free = BacktestEngine(panel, CostModel(0.0, 0.0, 0.0), **common).run()
    # 0.1% per-side fee, no tax/slippage so the arithmetic is exact.
    fee = 0.001
    costed = BacktestEngine(panel, CostModel(fee, 0.0, 0.0), **common).run()

    F = CAPITAL * pN / p0                 # frictionless final (buy then liquidate)
    assert free.final_value == pytest.approx(F, rel=1e-9)

    # Buy commission ~ fee*CAPITAL, sell commission ~ fee*F.
    expected_reduction = fee * (CAPITAL + F)
    assert (free.final_value - costed.final_value) == pytest.approx(
        expected_reduction, rel=1e-6
    )
    assert costed.final_value < free.final_value


# --------------------------------------------------------------------------- #
# Step 9 -- Test 3: two assets, equal weight, annual rebalance
# --------------------------------------------------------------------------- #
def test_two_asset_equal_weight_rebalance():
    dates = pd.bdate_range("2020-01-01", "2022-12-31")
    rng = np.random.default_rng(3)
    close1 = 10_000 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(dates))))
    close2 = 20_000 * np.exp(np.cumsum(rng.normal(0.0002, 0.012, len(dates))))
    panel = pd.DataFrame({1: close1, 2: close2}, index=dates)

    engine = BacktestEngine(
        panel,
        CostModel(0.0, 0.0, 0.0),
        target_func=lambda d: {1: 0.5, 2: 0.5},
        config=BacktestConfig(initial_capital=CAPITAL, rebalance_mode="1Y"),
    )
    result = engine.run()

    # One rebalance per calendar year (2020, 2021, 2022).
    assert len(result.rebalance_dates) == 3

    first_rb = result.rebalance_dates[0]
    first_positions = result.positions[
        result.positions["date"] == pd.Timestamp(first_rb).date()
    ]
    weights = dict(zip(first_positions["asset_id"], first_positions["weight"]))
    assert weights[1] == pytest.approx(0.5, abs=1e-9)
    assert weights[2] == pytest.approx(0.5, abs=1e-9)

    # Exactly two BUY trades on the first rebalance date.
    day_trades = result.trades[result.trades["date"] == pd.Timestamp(first_rb).date()]
    assert len(day_trades) == 2
    assert set(day_trades["side"]) == {"BUY"}

    # Manually verify the bought quantity of asset 1.
    expected_qty1 = (0.5 * CAPITAL) / panel[1].loc[first_rb]
    got_qty1 = float(day_trades[day_trades["asset_id"] == 1]["quantity"].iloc[0])
    assert got_qty1 == pytest.approx(expected_qty1, rel=1e-9)


# --------------------------------------------------------------------------- #
# Step 9 -- Test 4: delisting event triggers a 100% loss
# --------------------------------------------------------------------------- #
def test_delisting_triggers_full_loss():
    dates = pd.bdate_range("2020-01-01", periods=120)
    panel = pd.DataFrame({1: 100.0, 2: 100.0}, index=dates)  # flat prices
    first = dates[0]
    delist_date = dates[60]

    engine = BacktestEngine(
        panel,
        CostModel(0.0, 0.0, 0.0),
        targets={first: {1: 0.5, 2: 0.5}},
        delistings={2: delist_date},
        config=BacktestConfig(initial_capital=CAPITAL),
    )
    result = engine.run()

    # Before delisting: flat prices -> equity stays at initial capital.
    assert result.equity_curve.loc[dates[30]] == pytest.approx(CAPITAL, rel=1e-9)
    # After delisting: asset 2 sleeve (half the book) is wiped out.
    assert result.equity_curve.iloc[-1] == pytest.approx(CAPITAL / 2.0, rel=1e-9)

    # A 100%-loss "trade" is recorded for asset 2 at price 0.
    wipe = result.trades[(result.trades["asset_id"] == 2)
                         & (result.trades["execution_price"] == 0.0)]
    assert len(wipe) == 1
    assert 2 not in result.positions[
        result.positions["date"] == dates[-1].date()
    ]["asset_id"].values


# --------------------------------------------------------------------------- #
# Calendar utilities
# --------------------------------------------------------------------------- #
def test_next_trading_day_rolls_holiday_forward():
    days = pd.bdate_range("2021-01-04", "2021-12-31")  # Jan 1-3 not trading days
    rolled = next_trading_day(pd.Timestamp("2021-01-01"), days)
    assert rolled == days[0]
    assert rolled >= pd.Timestamp("2021-01-01")


def test_generate_rebalance_dates_counts():
    days = pd.bdate_range("2020-01-01", "2022-12-31")
    annual = generate_rebalance_dates(days, "1Y")
    semi = generate_rebalance_dates(days, "6M")
    assert len(annual) == 3            # one per year
    assert len(semi) == 6              # June + December each year
    assert all(d in days for d in annual)


def test_factor_mode_runs_end_to_end():
    from quant_portfolio_lab.data.synthetic import make_synthetic_market

    market = make_synthetic_market(n_assets=8, start="2019-01-01", end="2022-12-31")
    panel = market.prices.pivot(index="date", columns="asset_id", values="close")
    panel.index = pd.DatetimeIndex(panel.index)
    bench = market.benchmark.set_index("date")["close"]

    engine = BacktestEngine(
        panel,
        CostModel(),
        fundamentals=market.fundamentals,
        benchmark=bench,
        config=BacktestConfig(rebalance_mode="1Y", top_n=3, factor="pbr"),
    )
    result = engine.run()
    assert len(result.equity_curve) == len(panel)
    assert result.final_value > 0
    assert {"cagr", "volatility", "sharpe", "max_drawdown"} <= set(result.metrics)
    assert not result.trades.empty
