#!/usr/bin/env python3
"""Backtest a strategy over a past period, then create a current shortlist.

This is the operational bridge between research and action inside the project:
run a historical backtest over a user-specified window, evaluate pass/fail
thresholds, and only if the strategy passes, generate target weights as of the
latest available date or ``--as-of-date``.

Examples
--------
    python scripts/recommend.py --strategy value_momentum_quality \
        --backtest-start 2018-01-01 --backtest-end 2023-12-31 \
        --as-of-date 2024-12-31 --min-sharpe 0.5 --max-drawdown -0.35

    python scripts/recommend.py --synthetic --strategy defensive_value --min-cagr 0.03
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_portfolio_lab.backtest.cost_model import CostModel
from quant_portfolio_lab.backtest.engine import BacktestConfig, BacktestEngine
from quant_portfolio_lab.data.loaders import read_assets, read_benchmark, read_price_panel
from quant_portfolio_lab.data.synthetic import make_synthetic_market
from quant_portfolio_lab.portfolio import SUPPORTED_WEIGHTINGS
from quant_portfolio_lab.recommendation import (
    BacktestApprovalPolicy,
    build_recommendation_table,
    evaluate_backtest_policy,
    format_policy_checks,
)
from quant_portfolio_lab.strategies import (
    ADVANCED_STRATEGY_NAMES,
    ALL_STRATEGY_NAMES,
    BASIC_STRATEGIES,
    make_strategy_spec,
    weights_for_date,
)
from quant_portfolio_lab.visualization.charts import recommendation_weight_bar

DEFAULT_DB_PATH = Path("data") / "quant_portfolio_lab.duckdb"


def _db_helpers():
    from quant_portfolio_lab.data.db import get_connection, init_schema

    return get_connection, init_schema


def _load_inputs(args):
    if not args.synthetic and Path(args.db).exists():
        get_connection, init_schema = _db_helpers()
        con = get_connection(args.db)
        init_schema(con)
        panel = read_price_panel(con)
        fundamentals = con.execute("SELECT * FROM fundamental_snapshots").df()
        benchmark = read_benchmark(con, args.benchmark)
        assets = read_assets(con)
        con.close()
        if not panel.empty and not fundamentals.empty:
            panel.index = pd.DatetimeIndex(panel.index)
            return panel, fundamentals, benchmark if not benchmark.empty else None, assets
        print("[recommend] DuckDB found but missing prices/fundamentals; using synthetic data.")
    elif not args.synthetic:
        print(f"[recommend] database not found: {args.db}; using synthetic data.")

    market = make_synthetic_market(benchmark_id=args.benchmark)
    panel = market.prices.pivot(index="date", columns="asset_id", values="close")
    panel.index = pd.DatetimeIndex(panel.index)
    benchmark = market.benchmark.set_index("date")["close"]
    return panel, market.fundamentals, benchmark, market.assets


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


def _build_backtest(args, backtest_panel, full_panel, fundamentals, benchmark):
    cfg = BacktestConfig(
        initial_capital=args.capital,
        rebalance_mode=args.rebalance,
        top_n=args.top_n,
        benchmark_id=args.benchmark,
        weighting=args.weighting,
    )
    cost_model = CostModel(fee_rate=args.fee, tax_rate=args.tax, slippage_rate=args.slippage)

    if args.strategy in BASIC_STRATEGIES:
        cfg.factor = BASIC_STRATEGIES[args.strategy]
        return BacktestEngine(
            backtest_panel,
            cost_model,
            fundamentals=fundamentals,
            benchmark=benchmark,
            config=cfg,
        )

    if args.strategy in ADVANCED_STRATEGY_NAMES:
        spec = make_strategy_spec(args.strategy, top_n=args.top_n, weighting=args.weighting)
        return BacktestEngine(
            backtest_panel,
            cost_model,
            target_func=lambda d: weights_for_date(full_panel, fundamentals, d, spec),
            benchmark=benchmark,
            config=cfg,
        )

    raise ValueError(f"unknown strategy {args.strategy!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backtest a strategy, apply approval thresholds, then emit a shortlist"
    )
    parser.add_argument("--strategy", choices=list(ALL_STRATEGY_NAMES), default="low_pbr")
    parser.add_argument("--rebalance", choices=["1Y", "6M"], default="1Y")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--weighting", choices=list(SUPPORTED_WEIGHTINGS), default="equal")
    parser.add_argument("--benchmark", default="KOSPI")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--fee", type=float, default=0.001)
    parser.add_argument("--tax", type=float, default=0.0020)
    parser.add_argument("--slippage", type=float, default=0.002)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--backtest-start", default=None)
    parser.add_argument("--backtest-end", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--min-total-return", type=float, default=None)
    parser.add_argument("--min-cagr", type=float, default=None)
    parser.add_argument("--min-sharpe", type=float, default=None)
    parser.add_argument("--max-drawdown", type=float, default=None)
    parser.add_argument("--min-excess-total-return", type=float, default=None)
    parser.add_argument("--max-avg-turnover", type=float, default=None)
    parser.add_argument("--output-dir", default="data/recommendations")
    parser.add_argument(
        "--write-even-if-failed",
        action="store_true",
        help="write the shortlist even when one or more approval checks fails",
    )
    args = parser.parse_args()

    full_panel, fundamentals, benchmark_full, assets = _load_inputs(args)
    backtest_panel = _slice_by_date(full_panel, args.backtest_start, args.backtest_end)
    benchmark = _slice_by_date(benchmark_full, args.backtest_start, args.backtest_end)
    if backtest_panel.empty:
        raise SystemExit("[recommend] No price data remains after applying backtest dates")

    result = _build_backtest(args, backtest_panel, full_panel, fundamentals, benchmark).run()
    policy = BacktestApprovalPolicy(
        min_total_return=args.min_total_return,
        min_cagr=args.min_cagr,
        min_sharpe=args.min_sharpe,
        max_drawdown=args.max_drawdown,
        min_excess_total_return=args.min_excess_total_return,
        max_avg_turnover=args.max_avg_turnover,
    )
    approved, checks = evaluate_backtest_policy(result, policy)

    m = result.metrics
    print("\n=== Backtest approval ===")
    print(f"strategy     : {args.strategy}")
    print(f"period       : {m.get('start')} -> {m.get('end')}")
    print(f"total return : {m.get('total_return', float('nan')):.2%}")
    print(f"CAGR         : {m.get('cagr', float('nan')):.2%}")
    print(f"Sharpe       : {m.get('sharpe', float('nan')):.2f}")
    print(f"max drawdown : {m.get('max_drawdown', float('nan')):.2%}")
    print(f"avg turnover : {result.turnover:.2%}")
    print(f"checks       : {format_policy_checks(checks)}")
    print(f"approved     : {approved}")

    if not approved and not args.write_even_if_failed:
        print("\n[recommend] No shortlist written because the strategy did not pass the policy.")
        return 2

    recs = build_recommendation_table(
        args.strategy,
        full_panel,
        fundamentals,
        assets=assets,
        as_of_date=args.as_of_date,
        top_n=args.top_n,
        weighting=args.weighting,
    )
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{args.strategy}_recommendations.csv"
    html_path = out / f"{args.strategy}_target_weights.html"
    recs.to_csv(csv_path, index=False)
    recommendation_weight_bar(recs).write_html(html_path)

    print("\n=== Research shortlist ===")
    display_candidates = [
        "rank",
        "symbol",
        "name",
        "asset_id",
        "target_weight",
        "price",
        "pbr",
        "per",
    ]
    cols = [col for col in display_candidates if col in recs.columns]
    if cols:
        shown = recs[cols].copy()
        if "target_weight" in shown.columns:
            shown["target_weight"] = shown["target_weight"].map(lambda x: f"{x:.2%}")
        print(shown.to_string(index=False))
    print(f"\nrecommendations written to {csv_path}")
    print(f"target-weight chart written to {html_path}")
    print("research output only; not personalized investment advice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
