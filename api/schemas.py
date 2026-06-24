from typing import Literal

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy: str = "low_pbr"
    rebalance: Literal["1Y", "6M"] = "1Y"
    top_n: int = Field(default=20, ge=5, le=50)
    weighting: str = "equal"
    benchmark: str = "KOSPI"
    capital: float = 1_000_000.0
    fee: float = 0.001
    tax: float = 0.0020
    slippage: float = 0.002
    start: str | None = None
    end: str | None = None
    synthetic: bool = True