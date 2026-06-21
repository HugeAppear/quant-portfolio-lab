"""Unit tests for the transaction-cost engine (spec sections 7-9)."""

import math

import pytest

from quant_portfolio_lab.backtest.cost_model import BUY, SELL, CostModel, SlippageTier


@pytest.fixture
def model():
    # Spec defaults: 0.1% fee/side, 0.20% sell tax, 0.2% slippage.
    return CostModel(fee_rate=0.001, tax_rate=0.0020, slippage_rate=0.002)


def test_buy_execution_price_adds_slippage(model):
    assert model.execution_price(BUY, 10_000) == pytest.approx(10_000 * 1.002)


def test_sell_execution_price_subtracts_slippage(model):
    assert model.execution_price(SELL, 10_000) == pytest.approx(10_000 * 0.998)


def test_commission_is_rate_times_notional(model):
    assert model.commission(1_000_000) == pytest.approx(1_000.0)  # 0.1%


def test_transaction_tax_applies_to_sells_only(model):
    assert model.transaction_tax(BUY, 1_000_000) == 0.0
    assert model.transaction_tax(SELL, 1_000_000) == pytest.approx(2_000.0)  # 0.20%


def test_buy_trade_cashflow_is_negative_and_taxfree(model):
    tc = model.price_trade(BUY, quantity=100, close_price=10_000)
    assert tc.execution_price == pytest.approx(10_020.0)
    assert tc.gross_notional == pytest.approx(100 * 10_020.0)
    assert tc.transaction_tax == 0.0
    assert tc.commission == pytest.approx(tc.gross_notional * 0.001)
    assert tc.cash_flow == pytest.approx(-(tc.gross_notional + tc.commission))
    assert tc.cash_flow < 0


def test_sell_trade_cashflow_is_positive_with_tax(model):
    tc = model.price_trade(SELL, quantity=100, close_price=10_000)
    assert tc.execution_price == pytest.approx(9_980.0)
    expected = tc.gross_notional - tc.commission - tc.transaction_tax
    assert tc.cash_flow == pytest.approx(expected)
    assert tc.transaction_tax == pytest.approx(tc.gross_notional * 0.0020)
    assert tc.cash_flow > 0


def test_slippage_cost_matches_price_gap(model):
    tc = model.price_trade(BUY, quantity=100, close_price=10_000)
    assert tc.slippage_cost == pytest.approx(abs(tc.execution_price - 10_000) * 100)


def test_zero_cost_model_is_frictionless():
    free = CostModel(fee_rate=0.0, tax_rate=0.0, slippage_rate=0.0)
    tc = free.price_trade(BUY, quantity=50, close_price=200.0)
    assert tc.execution_price == 200.0
    assert tc.total_cost == 0.0
    assert tc.cash_flow == pytest.approx(-50 * 200.0)


def test_round_trip_total_cost_decomposition(model):
    buy = model.price_trade(BUY, 100, 10_000)
    sell = model.price_trade(SELL, 100, 10_000)
    # Net loss of a flat round trip = all frictional costs.
    net = buy.cash_flow + sell.cash_flow
    expected_costs = (buy.commission + sell.commission + sell.transaction_tax
                      + buy.slippage_cost + sell.slippage_cost)
    assert -net == pytest.approx(expected_costs)


def test_delisting_full_loss_residual_is_zero(model):
    assert model.apply_delisting(1_000_000) == 0.0


def test_delisting_partial_scenario_is_configurable():
    half = CostModel(delisting_loss=0.5)
    assert half.apply_delisting(1_000_000) == pytest.approx(500_000.0)


def test_slippage_tier_defaults():
    assert SlippageTier.LIQUID.default_rate < SlippageTier.ILLIQUID.default_rate


def test_negative_quantity_rejected(model):
    with pytest.raises(ValueError):
        model.price_trade(BUY, quantity=-1, close_price=100)


def test_negative_rate_rejected():
    with pytest.raises(ValueError):
        CostModel(fee_rate=-0.1)
    assert math.isfinite(CostModel().fee_rate)
