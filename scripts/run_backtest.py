#!/usr/bin/env python3
"""Run a backtest and emit result-page artifacts.

Examples
--------
    python scripts/run_backtest.py --synthetic --strategy low_pbr --rebalance 1Y --top-n 20
    python scripts/run_backtest.py --strategy value_momentum_quality --rebalance 6M --top-n 20
    python scripts/run_backtest.py --strategy defensive_value --start 2018-01-01 --end 2023-12-31
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_portfolio_lab.backtest.cost_model import CostModel
from quant_portfolio_lab.backtest.engine import BacktestConfig, BacktestEngine
from quant_portfolio_lab.data.loaders import read_benchmark, read_price_panel
from quant_portfolio_lab.data.synthetic import make_synthetic_market
from quant_portfolio_lab.portfolio import SUPPORTED_WEIGHTINGS
from quant_portfolio_lab.strategies import (
    ADVANCED_STRATEGY_NAMES,
    ALL_STRATEGY_NAMES,
    BASIC_STRATEGIES,
    make_strategy_spec,
    weights_for_date,
)
from quant_portfolio_lab.visualization.charts import (
    annual_return_table,
    cumulative_return_chart,
    drawdown_chart,
    portfolio_weight_bar,
    portfolio_weight_heatmap,
    portfolio_weight_treemap,
)

DEFAULT_DB_PATH = Path("data") / "quant_portfolio_lab.duckdb"


def _db_helpers():
    from quant_portfolio_lab.data.db import get_connection, init_schema

    return get_connection, init_schema


def _load_inputs(args):
    """Return (price_panel, fundamentals, benchmark) from DuckDB or synthetic."""
    if not args.synthetic and Path(args.db).exists():
        get_connection, init_schema = _db_helpers()
        con = get_connection(args.db)
        init_schema(con)

        panel = read_price_panel(con)
        fundamentals = con.execute("SELECT * FROM fundamental_snapshots").df()
        bench = read_benchmark(con, args.benchmark)

        price_sources = con.execute(
            """
            SELECT source, COUNT(DISTINCT asset_id) AS n_assets, COUNT(*) AS n_rows
            FROM price_bars
            GROUP BY source
            ORDER BY n_rows DESC
        """
        ).df()

        fundamental_sources = con.execute(
            """
            SELECT source, COUNT(DISTINCT asset_id) AS n_assets, COUNT(*) AS n_rows
            FROM fundamental_snapshots
            GROUP BY source
            ORDER BY n_rows DESC
        """
        ).df()

        benchmark_sources = con.execute(
            """
            SELECT benchmark_id, source, COUNT(*) AS n_rows
            FROM benchmark_prices
            WHERE benchmark_id = ?
            GROUP BY benchmark_id, source
        """,
            [args.benchmark],
        ).df()

        con.close()

        if not panel.empty and not fundamentals.empty:
            panel.index = pd.DatetimeIndex(panel.index)

            print("\n[run_backtest] DATA MODE: DuckDB / read data")
            print(f"[run_backtest] database: {args.db}")
            print(
                f"[run_backtest] price panel: {panel.shape[1]} assets "
                f"x {panel.shape[0]} trading days"
            )
            print(f"[run_backtest] fundamentals: {len(fundamentals)} rows")

            print("\n[run_backtest] price sources:")
            print(price_sources.to_string(index=False))
            if not fundamental_sources.empty:
                print("\n[run_backtest] fundamental sources:")
                print(fundamental_sources.to_string(index=False))

            if not benchmark_sources.empty:
                print("\n[run_backtest] benchmark sources:")
                print(benchmark_sources.to_string(index=False))
            else:
                print(f"\n[run_backtest] benchmark '{args.benchmark}' not found in DuckDB")

            return panel, fundamentals, (bench if not bench.empty else None)

        print("\n[run_backtest] WARNING: DuckDB was found, but prices or fundamentals were empty.")
        print("[run_backtest] Falling back to synthetic data.")

    else:
        if args.synthetic:
            print("\n[run_backtest] DATA MODE: forced synthetic data because --synthetic was used")
        else:
            print(f"\n[run_backtest] WARNING: database not found: {args.db}")
            print("[run_backtest] Falling back to synthetic data.")

    market = make_synthetic_market(benchmark_id=args.benchmark)
    panel = market.prices.pivot(index="date", columns="asset_id", values="close")
    panel.index = pd.DatetimeIndex(panel.index)
    bench = market.benchmark.set_index("date")["close"]

    print(
        f"[run_backtest] synthetic price panel: {panel.shape[1]} assets "
        f"x {panel.shape[0]} trading days"
    )
    print(f"[run_backtest] synthetic fundamentals: {len(market.fundamentals)} rows")
    print(f"[run_backtest] synthetic benchmark: {len(bench)} rows")

    return panel, market.fundamentals, bench


def _slice_by_date(obj, start=None, end=None):
    if obj is None or len(obj) == 0:
        return obj
    out = obj.copy()
    out.index = pd.DatetimeIndex(out.index)
    if start is not None:
        out = out.loc[out.index >= pd.Timestamp(start)]
    if end is not None:
        out = out.loc[out.index <= pd.Timestamp(end)]
    return out


def _build_engine(args, panel, full_panel, fundamentals, benchmark):
    cost_model = CostModel(fee_rate=args.fee, tax_rate=args.tax, slippage_rate=args.slippage)
    cfg = BacktestConfig(
        initial_capital=args.capital,
        rebalance_mode=args.rebalance,
        top_n=args.top_n,
        benchmark_id=args.benchmark,
        weighting=args.weighting,
    )

    if args.strategy in BASIC_STRATEGIES:
        cfg.factor = BASIC_STRATEGIES[args.strategy]
        return BacktestEngine(
            panel,
            cost_model,
            fundamentals=fundamentals,
            benchmark=benchmark,
            config=cfg,
        )

    if args.strategy in ADVANCED_STRATEGY_NAMES:
        spec = make_strategy_spec(args.strategy, top_n=args.top_n, weighting=args.weighting)
        return BacktestEngine(
            panel,
            cost_model,
            target_func=lambda d: weights_for_date(full_panel, fundamentals, d, spec),
            benchmark=benchmark,
            config=cfg,
        )

    raise ValueError(f"unknown strategy {args.strategy!r}")


def _persist_run(db, result, args, run_id):
    get_connection, init_schema = _db_helpers()
    con = get_connection(db)
    init_schema(con)
    con.execute(
        "INSERT OR REPLACE INTO backtest_runs VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            run_id,
            args.strategy,
            "kr_common_equity",
            args.rebalance,
            args.benchmark,
            args.fee,
            f"sell_tax={args.tax}",
            f"flat={args.slippage}",
            "100pct_loss",
            datetime.now(UTC).replace(tzinfo=None),
        ],
    )
    if not result.positions.empty:
        pos = result.positions.copy()
        pos.insert(0, "run_id", run_id)
        con.register(
            "_pos",
            pos[["run_id", "date", "asset_id", "weight", "quantity", "market_value"]],
        )
        con.execute("INSERT INTO backtest_positions SELECT * FROM _pos")
        con.unregister("_pos")
    if not result.trades.empty:
        trd = result.trades.copy()
        trd.insert(0, "run_id", run_id)
        con.register(
            "_trd",
            trd[
                [
                    "run_id",
                    "date",
                    "asset_id",
                    "side",
                    "quantity",
                    "execution_price",
                    "gross_notional",
                    "commission",
                    "transaction_tax",
                    "slippage_cost",
                ]
            ],
        )
        con.execute("INSERT INTO backtest_trades SELECT * FROM _trd")
        con.unregister("_trd")
    con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a backtest")
    parser.add_argument("--strategy", choices=list(ALL_STRATEGY_NAMES), default="low_pbr")
    parser.add_argument("--rebalance", choices=["1Y", "6M"], default="1Y")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--weighting", choices=list(SUPPORTED_WEIGHTINGS), default="equal")
    parser.add_argument("--benchmark", default="KOSPI")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--fee", type=float, default=0.001)
    parser.add_argument("--tax", type=float, default=0.0020)
    parser.add_argument("--slippage", type=float, default=0.002)
    parser.add_argument("--start", default=None, help="optional backtest start date, YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="optional backtest end date, YYYY-MM-DD")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    full_panel, fundamentals, full_bench = _load_inputs(args)
    panel = _slice_by_date(full_panel, args.start, args.end)
    bench = _slice_by_date(full_bench, args.start, args.end) if full_bench is not None else None
    if panel.empty:
        raise SystemExit("[run_backtest] No price data remains after applying --start/--end")

    engine = _build_engine(args, panel, full_panel, fundamentals, bench)
    result = engine.run()
    m = result.metrics

    print("\n=== Backtest result ===")
    print(f"strategy        : {args.strategy} ({args.rebalance}, top {args.top_n})")
    print(f"weighting       : {args.weighting}")
    print(f"period          : {m.get('start')} -> {m.get('end')}")
    print(f"final value     : {result.final_value:,.0f}")
    print(f"total return    : {m.get('total_return', float('nan')):.2%}")
    print(f"CAGR            : {m.get('cagr', float('nan')):.2%}")
    print(f"volatility      : {m.get('volatility', float('nan')):.2%}")
    print(f"Sharpe          : {m.get('sharpe', float('nan')):.2f}")
    print(f"max drawdown    : {m.get('max_drawdown', float('nan')):.2%}")
    print(f"avg turnover    : {result.turnover:.2%}")
    print(f"# trades        : {len(result.trades)}")
    if "benchmark_total_return" in m:
        print(f"benchmark return: {m['benchmark_total_return']:.2%}")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cumulative_return_chart(result.equity_curve, result.benchmark).write_html(
        out / "cumulative_return.html"
    )
    drawdown_chart(result.equity_curve).write_html(out / "drawdown.html")
    annual_return_table(result.equity_curve, result.benchmark).write_html(
        out / "annual_returns.html"
    )
    portfolio_weight_bar(result.positions).write_html(out / "portfolio_weights.html")
    portfolio_weight_treemap(result.positions).write_html(out / "portfolio_treemap.html")
    portfolio_weight_heatmap(result.positions).write_html(out / "portfolio_weight_heatmap.html")
    result.equity_curve.to_csv(out / "equity_curve.csv")
    print(f"\nartifacts written to {out}/")

    if not args.no_persist:
        run_id = uuid.uuid4().hex[:12]
        _persist_run(args.db, result, args, run_id)
        print(f"run persisted as run_id={run_id} -> {args.db}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
