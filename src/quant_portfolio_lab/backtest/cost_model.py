"""Transaction-cost engine (spec sections 7-9).

Kept deliberately modular -- it is *not* hard-coded inside the backtest loop, so
the same model can be reused and reconfigured independently.

Model
-----
- Brokerage fee : 0.1% per side, on both buys and sells.
- Transaction tax: 0.20% on **sell** trades only (configurable per market/date).
- Slippage      : applied to the execution price.

    Buy execution price  = close_price * (1 + slippage_rate)
    Sell execution price = close_price * (1 - slippage_rate)
    Commission           = abs(trade_notional) * fee_rate
    Transaction tax      = sell_notional * tax_rate    (sells only)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

BUY = "BUY"
SELL = "SELL"


class SlippageTier(str, Enum):
    """Liquidity tiers with default slippage assumptions (spec section 8)."""

    LIQUID = "liquid"        # 0.1%-0.3% band
    ILLIQUID = "illiquid"    # 0.5%-1.0% band

    @property
    def default_rate(self) -> float:
        return {SlippageTier.LIQUID: 0.002, SlippageTier.ILLIQUID: 0.0075}[self]


@dataclass(frozen=True)
class TradeCost:
    """Result of pricing a single trade through the cost model."""

    side: str
    quantity: float
    close_price: float
    execution_price: float
    gross_notional: float       # execution_price * quantity (>= 0)
    commission: float
    transaction_tax: float
    slippage_cost: float
    cash_flow: float            # signed: negative on buys, positive on sells

    @property
    def total_cost(self) -> float:
        """Frictional cost vs. a frictionless fill at the close price."""
        return self.commission + self.transaction_tax + self.slippage_cost


class CostModel:
    """Configurable brokerage / tax / slippage model."""

    def __init__(
        self,
        fee_rate: float = 0.001,
        tax_rate: float = 0.0020,
        slippage_rate: float = 0.002,
        delisting_loss: float = 1.0,
    ) -> None:
        if min(fee_rate, tax_rate, slippage_rate) < 0:
            raise ValueError("cost rates must be non-negative")
        self.fee_rate = fee_rate
        self.tax_rate = tax_rate
        self.slippage_rate = slippage_rate
        self.delisting_loss = delisting_loss

    # -- price / component helpers -------------------------------------------
    def execution_price(self, side: str, close_price: float,
                        slippage_rate: float | None = None) -> float:
        rate = self.slippage_rate if slippage_rate is None else slippage_rate
        side = side.upper()
        if side == BUY:
            return close_price * (1.0 + rate)
        if side == SELL:
            return close_price * (1.0 - rate)
        raise ValueError(f"side must be BUY or SELL, got {side!r}")

    def commission(self, notional: float) -> float:
        return abs(notional) * self.fee_rate

    def transaction_tax(self, side: str, sell_notional: float) -> float:
        return abs(sell_notional) * self.tax_rate if side.upper() == SELL else 0.0

    # -- full trade ----------------------------------------------------------
    def price_trade(
        self,
        side: str,
        quantity: float,
        close_price: float,
        slippage_rate: float | None = None,
    ) -> TradeCost:
        """Price one trade and return the full :class:`TradeCost` breakdown.

        ``quantity`` is the (positive) number of shares traded.
        """
        side = side.upper()
        if quantity < 0:
            raise ValueError("quantity must be non-negative; use side to set direction")
        rate = self.slippage_rate if slippage_rate is None else slippage_rate

        exec_price = self.execution_price(side, close_price, rate)
        gross_notional = exec_price * quantity
        commission = self.commission(gross_notional)
        tax = self.transaction_tax(side, gross_notional)
        slippage_cost = abs(exec_price - close_price) * quantity

        if side == BUY:
            cash_flow = -(gross_notional + commission)
        else:  # SELL
            cash_flow = gross_notional - commission - tax

        return TradeCost(
            side=side,
            quantity=quantity,
            close_price=close_price,
            execution_price=exec_price,
            gross_notional=gross_notional,
            commission=commission,
            transaction_tax=tax,
            slippage_cost=slippage_cost,
            cash_flow=cash_flow,
        )

    # -- scenario ------------------------------------------------------------
    def apply_delisting(self, market_value: float) -> float:
        """Residual value of a position hit by a delisting event.

        Default conservative scenario: 100% loss -> residual 0.
        """
        return market_value * (1.0 - self.delisting_loss)
