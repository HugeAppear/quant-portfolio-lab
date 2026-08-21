"""Pydantic request/response models for the web GUI API.

Field names are camelCase on purpose: they mirror ``frontend/src/api/types.ts``
one-to-one so the TypeScript client needs no translation layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..portfolio import SUPPORTED_WEIGHTINGS
from ..strategies import ALL_STRATEGY_NAMES

StrategyId = Literal[
    "low_pbr", "low_per", "value_momentum_quality", "defensive_value", "momentum_lowvol"
]
RebalanceId = Literal["1Y", "6M"]
WeightingId = Literal["equal", "score", "inverse_vol"]
DataMode = Literal["auto", "synthetic"]
RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

# Sanity guards: keep the Literal types above in sync with the engine.
assert set(ALL_STRATEGY_NAMES) == {
    "low_pbr", "low_per", "value_momentum_quality", "defensive_value", "momentum_lowvol"
}
assert set(SUPPORTED_WEIGHTINGS) == {"equal", "score", "inverse_vol"}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class RunConfig(BaseModel):
    strategy: StrategyId = "low_pbr"
    rebalance: RebalanceId = "1Y"
    topN: int = Field(default=20, ge=2, le=50)
    weighting: WeightingId = "equal"
    benchmark: str = "KOSPI"
    startDate: str | None = None  # ISO yyyy-mm-dd
    endDate: str | None = None
    initialCapital: float = Field(default=10_000_000.0, gt=0)
    feeBps: float = Field(default=10.0, ge=0)       # 10 bps = 0.10%
    taxBps: float = Field(default=20.0, ge=0)       # sell-side transaction tax
    slippageBps: float = Field(default=20.0, ge=0)
    dataMode: DataMode = "auto"


class Metrics(BaseModel):
    totalReturn: float | None = None
    cagr: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    maxDrawdown: float | None = None
    calmar: float | None = None
    winRate: float | None = None
    turnover: float | None = None          # average per-rebalance turnover
    finalValue: float | None = None
    benchmarkTotalReturn: float | None = None
    benchmarkCagr: float | None = None
    excessCagr: float | None = None
    benchmarkMaxDrawdown: float | None = None


class EquityPoint(BaseModel):
    date: str
    equity: float
    benchmark: float | None = None
    drawdown: float | None = None


class Holding(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    weight: float
    shares: float | None = None
    value: float | None = None


class AllocationPoint(BaseModel):
    date: str
    weights: dict[str, float]


class RunSummary(BaseModel):
    id: str
    createdAt: str
    status: RunStatus
    strategy: StrategyId
    rebalance: RebalanceId
    topN: int
    weighting: WeightingId
    dataModeUsed: str | None = None       # "duckdb" | "synthetic"
    metrics: Metrics | None = None


class Run(RunSummary):
    config: RunConfig
    equityCurve: list[EquityPoint] | None = None
    holdings: list[Holding] | None = None
    allocation: list[AllocationPoint] | None = None
    error: str | None = None


class DashboardData(BaseModel):
    asOf: str
    runCount: int
    latestRun: Run | None = None


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------

class FactorSignal(BaseModel):
    name: str
    value: float   # percentile score in [0, 1]


class ShortlistItem(BaseModel):
    rank: int
    ticker: str
    name: str
    sector: str | None = None
    score: float | None = None
    targetWeight: float | None = None
    price: float | None = None
    per: float | None = None
    pbr: float | None = None
    signals: list[FactorSignal] = []


class Shortlist(BaseModel):
    generatedAt: str
    asOf: str
    strategy: StrategyId
    weighting: WeightingId
    dataModeUsed: str
    items: list[ShortlistItem]


# ---------------------------------------------------------------------------
# Data health / data jobs
# ---------------------------------------------------------------------------

class DataHealthCheck(BaseModel):
    source: str
    status: Literal["ok", "warning", "error"]
    lastUpdated: str | None = None
    rows: int | None = None
    symbols: int | None = None
    staleDays: int | None = None
    message: str | None = None


class DataHealth(BaseModel):
    checkedAt: str
    dbPath: str
    checks: list[DataHealthCheck]


class DataLoadRequest(BaseModel):
    kind: Literal["prices", "fundamentals", "all"] = "all"
    start: str = "2018-01-01"
    end: str | None = None
    universeSize: int = Field(default=100, ge=1, le=500)
    synthetic: bool = False


class DataJob(BaseModel):
    id: str
    kind: str
    status: Literal["queued", "running", "completed", "failed"]
    createdAt: str
    finishedAt: str | None = None
    logTail: list[str] = []
    error: str | None = None
