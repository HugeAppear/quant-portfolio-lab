# Quant Portfolio Lab v0.1

A personal analytics and research platform that organizes, processes, backtests,
and visualizes financial data. It **does not** provide personalized investment
recommendations, act as a fiduciary, or execute trades. All investment decisions
remain with the user.

The v0.1 goal is **correctness**, not optimization. See
[`specs/quant_portfolio_lab_v0_1_policy.md`](specs/quant_portfolio_lab_v0_1_policy.md)
for the full policy and [`specs/backtest_policy.yaml`](specs/backtest_policy.yaml)
for the machine-readable configuration.

## What's implemented

- **DuckDB schema** for assets, prices, fundamentals, factor snapshots,
  benchmarks, and backtest results (`src/quant_portfolio_lab/data`).
- **Valuation factors** PER/PBR with the exclusion rules (EPS/BPS ≤ 0 or missing)
  and **point-in-time** validity (`report_date ≤ rebalance_date`) to prevent
  look-ahead bias (`src/quant_portfolio_lab/factors`).
- **Transaction-cost engine** — brokerage fee, sell-side transaction tax, and
  slippage — kept modular, outside the backtest loop
  (`src/quant_portfolio_lab/backtest/cost_model.py`).
- **Backtest engine** with 6M / 1Y rebalancing, holiday roll-forward, equal-weight
  top-N portfolios, and a 100%-loss delisting scenario
  (`src/quant_portfolio_lab/backtest/engine.py`).
- **Metrics** — CAGR, volatility, Sharpe, max drawdown, turnover.
- **Plotly charts** — cumulative return vs benchmark, drawdown, annual returns.
- **Streamlit** result page prototype (`src/quant_portfolio_lab/app`).

## Quick start

```bash
# 1. Install (editable) with dev + data extras
pip install -e ".[dev,data]"

# 2. Run the test suite (fully offline; uses synthetic data)
pytest

# 3. Run a backtest on synthetic data -- no network needed
python scripts/run_backtest.py --synthetic --strategy low_pbr --rebalance 1Y --top-n 20

# 4. (Optional) Pull real Korean data into DuckDB, then backtest
python scripts/load_prices.py --start 2018-01-01 --end 2024-12-31
python scripts/load_fundamentals.py --start 2018-01-01 --end 2024-12-31
python scripts/run_backtest.py --strategy low_pbr --rebalance 1Y --benchmark KOSPI
```

The data loaders use **pykrx** (Korean prices + PER/PBR/EPS/BPS fundamentals) and
**FinanceDataReader** (benchmarks). If those packages or the network are
unavailable, every script falls back to synthetic data so the repo is runnable
end-to-end offline.

## Project layout

```
src/quant_portfolio_lab/
  data/          DuckDB schema, loaders, synthetic generator
  factors/       PER/PBR valuation, exclusions, point-in-time validity
  portfolio/     top-N selection, equal weighting
  backtest/      calendar, cost_model, engine, metrics
  visualization/ Plotly charts
  app/           Streamlit prototype
scripts/         load_prices, load_fundamentals, run_backtest
tests/           engine, cost-model, factor unit tests (Step 9 validation)
notebooks/       exploratory_analysis.ipynb
```

## Validation (Step 9)

`tests/` implements the six required checks: buy-and-hold equivalence, fee
reduction, two-asset equal-weight rebalance, delisting 100% loss, EPS/BPS
exclusion, and no use of future financial statements.

## Disclaimer

For research and educational use only. Not investment advice.
