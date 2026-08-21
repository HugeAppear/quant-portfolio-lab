"""Core services behind the web GUI: run execution, shortlist, data health."""

from __future__ import annotations

import math
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ..backtest.cost_model import CostModel
from ..backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from ..backtest.metrics import drawdown_series
from ..data.db import get_connection, init_schema
from ..recommendation import build_recommendation_table
from ..strategies import (
    ADVANCED_STRATEGY_NAMES,
    BASIC_STRATEGIES,
    make_strategy_spec,
    weights_for_date,
)
from .inputs import (
    DB_LOCK,
    MarketInputs,
    asset_labels,
    load_market_inputs,
    resolve_db_path,
    slice_by_date,
)
from .schemas import (
    AllocationPoint,
    DataHealth,
    DataHealthCheck,
    EquityPoint,
    FactorSignal,
    Holding,
    Metrics,
    Run,
    RunConfig,
    Shortlist,
    ShortlistItem,
)
from .store import RunStore


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clean(v: float | None) -> float | None:
    """None-out NaN/inf so the JSON payload stays valid."""
    if v is None:
        return None
    v = float(v)
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------------------
# Backtest execution
# ---------------------------------------------------------------------------

def _build_engine(config: RunConfig, inputs: MarketInputs) -> BacktestEngine:
    panel = slice_by_date(inputs.panel, config.startDate, config.endDate)
    bench = (
        slice_by_date(inputs.benchmark, config.startDate, config.endDate)
        if inputs.benchmark is not None
        else None
    )
    if panel is None or panel.empty:
        raise ValueError("No price data remains after applying the start/end dates.")

    cfg = BacktestConfig(
        initial_capital=config.initialCapital,
        rebalance_mode=config.rebalance,
        top_n=config.topN,
        benchmark_id=config.benchmark,
        weighting=config.weighting,
    )
    cost_model = CostModel(
        fee_rate=config.feeBps / 10_000.0,
        tax_rate=config.taxBps / 10_000.0,
        slippage_rate=config.slippageBps / 10_000.0,
    )

    if config.strategy in BASIC_STRATEGIES:
        cfg.factor = BASIC_STRATEGIES[config.strategy]
        return BacktestEngine(
            panel, cost_model,
            fundamentals=inputs.fundamentals, benchmark=bench, config=cfg,
        )
    if config.strategy in ADVANCED_STRATEGY_NAMES:
        spec = make_strategy_spec(
            config.strategy, top_n=config.topN, weighting=config.weighting
        )
        full_panel = inputs.panel
        fundamentals = inputs.fundamentals
        return BacktestEngine(
            panel, cost_model,
            target_func=lambda d: weights_for_date(full_panel, fundamentals, d, spec),
            benchmark=bench, config=cfg,
        )
    raise ValueError(f"unknown strategy {config.strategy!r}")


def _extended_metrics(result: BacktestResult) -> Metrics:
    m = result.metrics
    equity = result.equity_curve
    rets = equity.pct_change().dropna()

    sortino = None
    downside = rets[rets < 0]
    if len(rets) > 1 and len(downside) > 0:
        downside_dev = float(np.sqrt((downside**2).mean()) * np.sqrt(252))
        if downside_dev > 0:
            sortino = float(rets.mean() * 252 / downside_dev)

    cagr = m.get("cagr")
    max_dd = m.get("max_drawdown")
    calmar = None
    if cagr is not None and max_dd is not None and math.isfinite(max_dd) and max_dd < 0:
        calmar = float(cagr / abs(max_dd))

    win_rate = float((rets > 0).mean()) if len(rets) else None

    return Metrics(
        totalReturn=_clean(m.get("total_return")),
        cagr=_clean(cagr),
        volatility=_clean(m.get("volatility")),
        sharpe=_clean(m.get("sharpe")),
        sortino=_clean(sortino),
        maxDrawdown=_clean(max_dd),
        calmar=_clean(calmar),
        winRate=_clean(win_rate),
        turnover=_clean(result.turnover),
        finalValue=_clean(result.final_value),
        benchmarkTotalReturn=_clean(m.get("benchmark_total_return")),
        benchmarkCagr=_clean(m.get("benchmark_cagr")),
        excessCagr=_clean(m.get("excess_cagr")),
        benchmarkMaxDrawdown=_clean(m.get("benchmark_max_drawdown")),
    )


def _equity_points(result: BacktestResult, max_points: int = 1500) -> list[EquityPoint]:
    equity = result.equity_curve
    dd = drawdown_series(equity)
    bench = result.benchmark
    if bench is not None and not bench.dropna().empty:
        b = bench.dropna()
        # Rebase the benchmark to the strategy's starting capital.
        bench = bench / float(b.iloc[0]) * float(equity.iloc[0])

    # Downsample long series but always keep the final observation.
    idx = equity.index
    if len(idx) > max_points:
        step = int(np.ceil(len(idx) / max_points))
        keep = list(range(0, len(idx), step))
        if keep[-1] != len(idx) - 1:
            keep.append(len(idx) - 1)
        idx = idx[keep]

    points = []
    for d in idx:
        b = None
        if bench is not None:
            bv = bench.get(d)
            b = _clean(float(bv)) if bv is not None and not pd.isna(bv) else None
        points.append(
            EquityPoint(
                date=pd.Timestamp(d).date().isoformat(),
                equity=float(equity.loc[d]),
                benchmark=b,
                drawdown=_clean(float(dd.loc[d])),
            )
        )
    return points


def _holdings_and_allocation(
    result: BacktestResult, inputs: MarketInputs
) -> tuple[list[Holding], list[AllocationPoint]]:
    symbols, names, segments = asset_labels(inputs.assets)
    positions = result.positions
    if positions is None or positions.empty:
        return [], []

    pos = positions.copy()
    pos["date"] = pd.to_datetime(pos["date"])

    allocation = []
    for d, grp in pos.groupby("date"):
        weights = {
            symbols.get(int(r.asset_id), str(int(r.asset_id))): float(r.weight)
            for r in grp.itertuples(index=False)
        }
        allocation.append(
            AllocationPoint(date=pd.Timestamp(d).date().isoformat(), weights=weights)
        )
    allocation.sort(key=lambda a: a.date)

    last_date = pos["date"].max()
    last = pos[pos["date"] == last_date]
    holdings = [
        Holding(
            ticker=symbols.get(int(r.asset_id), str(int(r.asset_id))),
            name=names.get(int(r.asset_id)),
            sector=segments.get(int(r.asset_id)),
            weight=float(r.weight),
            shares=float(r.quantity),
            value=float(r.market_value),
        )
        for r in last.itertuples(index=False)
    ]
    holdings.sort(key=lambda h: h.weight, reverse=True)
    return holdings, allocation


class RunManager:
    """Owns the run lifecycle: queue, execute in a worker thread, persist."""

    def __init__(self, store: RunStore | None = None) -> None:
        self.store = store or RunStore()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def submit(self, config: RunConfig) -> Run:
        run = Run(
            id=uuid.uuid4().hex[:12],
            createdAt=_now_iso(),
            status="queued",
            strategy=config.strategy,
            rebalance=config.rebalance,
            topN=config.topN,
            weighting=config.weighting,
            config=config,
        )
        self.store.create(run)
        self._executor.submit(self._execute, run.id, config)
        return run

    def cancel(self, run_id: str) -> Run | None:
        run = self.store.get(run_id)
        if run is None:
            return None
        if run.status == "queued":
            with self._lock:
                self._cancelled.add(run_id)
            run.status = "cancelled"
            self.store.update(run)
        return run

    def _execute(self, run_id: str, config: RunConfig) -> None:
        with self._lock:
            if run_id in self._cancelled:
                self._cancelled.discard(run_id)
                return
        run = self.store.get(run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        self.store.update(run)
        try:
            inputs = load_market_inputs(
                config.benchmark, data_mode=config.dataMode, db_path=self.store.db_path
            )
            result = _build_engine(config, inputs).run()
            holdings, allocation = _holdings_and_allocation(result, inputs)
            run.dataModeUsed = inputs.mode
            run.metrics = _extended_metrics(result)
            run.equityCurve = _equity_points(result)
            run.holdings = holdings
            run.allocation = allocation
            run.status = "completed"
        except Exception as exc:  # surface the failure in the GUI
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
        self.store.update(run)


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------

_SIGNAL_COLUMNS = [
    ("value", "value_score"),
    ("momentum", "momentum_score"),
    ("low vol", "low_vol_score"),
    ("quality", "quality_score"),
]


def build_shortlist(
    strategy: str,
    *,
    top_n: int = 20,
    weighting: str = "equal",
    as_of_date: str | None = None,
    data_mode: str = "auto",
    benchmark: str = "KOSPI",
    db_path=None,
) -> Shortlist:
    inputs = load_market_inputs(benchmark, data_mode=data_mode, db_path=db_path)
    recs = build_recommendation_table(
        strategy,
        inputs.panel,
        inputs.fundamentals,
        assets=inputs.assets,
        as_of_date=as_of_date,
        top_n=top_n,
        weighting=weighting,
    )

    items: list[ShortlistItem] = []
    as_of = ""
    for row in recs.to_dict("records"):
        as_of = str(row.get("as_of_date", as_of))
        signals = []
        for label, col in _SIGNAL_COLUMNS:
            v = row.get(col)
            if v is not None and not pd.isna(v):
                signals.append(FactorSignal(name=label, value=float(v)))
        score = row.get("composite_score")
        if score is None or pd.isna(score):
            # Basic strategies: use the ranked factor itself as the score.
            score = row.get("pbr") if strategy == "low_pbr" else row.get("per")
        items.append(
            ShortlistItem(
                rank=int(row.get("rank", len(items) + 1)),
                ticker=str(row.get("symbol") or row.get("asset_id")),
                name=str(row.get("name") or ""),
                sector=(str(row["market_segment"])
                        if row.get("market_segment") is not None
                        and not pd.isna(row.get("market_segment")) else None),
                score=_clean(score if score is None or not pd.isna(score) else None),
                targetWeight=_clean(row.get("target_weight")),
                price=_clean(row.get("price")),
                per=_clean(row.get("per") if not pd.isna(row.get("per", np.nan)) else None),
                pbr=_clean(row.get("pbr") if not pd.isna(row.get("pbr", np.nan)) else None),
                signals=signals,
            )
        )
    return Shortlist(
        generatedAt=_now_iso(),
        asOf=as_of or _now_iso()[:10],
        strategy=strategy,  # type: ignore[arg-type]
        weighting=weighting,  # type: ignore[arg-type]
        dataModeUsed=inputs.mode,
        items=items,
    )


# ---------------------------------------------------------------------------
# Data health
# ---------------------------------------------------------------------------

def _table_check(con, source: str, table: str, date_col: str | None) -> DataHealthCheck:
    try:
        rows = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        symbols = None
        if table in ("price_bars", "fundamental_snapshots"):
            symbols = int(
                con.execute(f"SELECT COUNT(DISTINCT asset_id) FROM {table}").fetchone()[0]
            )
        elif table == "assets":
            symbols = rows
        last, stale = None, None
        if date_col and rows:
            last_val = con.execute(f"SELECT MAX({date_col}) FROM {table}").fetchone()[0]
            if last_val is not None:
                last_ts = pd.Timestamp(last_val)
                last = last_ts.date().isoformat()
                stale = max(0, (pd.Timestamp.today().normalize() - last_ts.normalize()).days)
        if rows == 0:
            status, message = "warning", "Table is empty — load data or run in synthetic mode."
        elif stale is not None and stale > 14:
            status, message = "warning", f"Latest row is {stale} days old."
        else:
            status, message = "ok", None
        return DataHealthCheck(
            source=source, status=status, lastUpdated=last, rows=rows,
            symbols=symbols, staleDays=stale, message=message,
        )
    except Exception as exc:
        return DataHealthCheck(source=source, status="error", message=str(exc))


def build_data_health(db_path=None) -> DataHealth:
    path = resolve_db_path(db_path)
    checks: list[DataHealthCheck] = []

    if not path.exists():
        checks.append(DataHealthCheck(
            source="duckdb file", status="warning",
            message=f"{path} not found — the GUI will use synthetic data until you load real data.",
        ))
    else:
        with DB_LOCK:
            con = get_connection(path)
            try:
                init_schema(con)
                checks.append(_table_check(con, "assets", "assets", None))
                checks.append(_table_check(con, "prices (price_bars)", "price_bars", "date"))
                checks.append(_table_check(
                    con, "fundamentals (EPS/BPS)", "fundamental_snapshots", "report_date"
                ))
                checks.append(_table_check(
                    con, "benchmark prices", "benchmark_prices", "date"
                ))
            finally:
                con.close()

    for pkg, label in (("pykrx", "pykrx (KRX loader)"),
                       ("FinanceDataReader", "FinanceDataReader (benchmarks)")):
        try:
            __import__(pkg)
            checks.append(DataHealthCheck(source=label, status="ok", message="importable"))
        except Exception:
            checks.append(DataHealthCheck(
                source=label, status="warning",
                message="Not installed — real-data loading unavailable "
                        "(pip install -e '.[data]').",
            ))

    return DataHealth(checkedAt=_now_iso(), dbPath=str(path), checks=checks)
