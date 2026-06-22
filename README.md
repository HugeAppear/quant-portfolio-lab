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
- **Advanced strategy layer** for multi-factor value/momentum/quality/low-volatility
  portfolios (`src/quant_portfolio_lab/strategies`).
- **Research shortlist workflow** that gates recommendations behind backtest
  thresholds (`scripts/recommend.py`).
- **Portfolio configuration charts**: final weights, treemap, and weight heatmap
  (`src/quant_portfolio_lab/visualization/charts.py`).

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

## Advanced strategies

The original `low_pbr` and `low_per` strategies are still supported. Additional
strategy names are available through the new strategy layer:

- `value_momentum_quality` — composite of cheap valuation, 12-1 momentum, and
  EPS/BPS quality proxy.
- `defensive_value` — value strategy tilted toward lower realized volatility.
- `momentum_lowvol` — price momentum plus lower realized volatility.

Run an advanced backtest and write the usual return charts plus allocation
charts:

```bash
python scripts/run_backtest.py \
  --strategy value_momentum_quality \
  --rebalance 6M \
  --top-n 20 \
  --weighting score \
  --start 2018-01-01 \
  --end 2024-12-31
```

Available weighting modes are `equal`, `score`, and `inverse_vol`.

## Backtest-gated research shortlist

Use `scripts/recommend.py` when you want an immediate current shortlist only
after a strategy passes thresholds over a historical backtest window. Example:

```bash
python scripts/recommend.py \
  --strategy defensive_value \
  --backtest-start 2018-01-01 \
  --backtest-end 2023-12-31 \
  --as-of-date 2024-12-31 \
  --top-n 20 \
  --weighting inverse_vol \
  --min-sharpe 0.5 \
  --max-drawdown -0.35
```

If every configured threshold passes, the script writes a CSV shortlist and a
target-weight HTML chart to `data/recommendations/`. If any threshold fails, it
prints the failed checks and writes nothing unless `--write-even-if-failed` is
used.

The shortlist is a reproducible research output from the strategy, not
personalized investment advice.

The data loaders use **pykrx** (Korean prices + PER/PBR/EPS/BPS fundamentals) and
**FinanceDataReader** (benchmarks). If those packages or the network are
unavailable, every script falls back to synthetic data so the repo is runnable
end-to-end offline.

## Project layout

```
src/quant_portfolio_lab/
  data/          DuckDB schema, loaders, synthetic generator
  factors/       PER/PBR valuation, exclusions, point-in-time validity
  portfolio/     top-N selection, equal/score/inverse-vol weighting
  strategies/    advanced point-in-time composite strategy definitions
  recommendation.py backtest approval gates and research shortlist builder
  backtest/      calendar, cost_model, engine, metrics
  visualization/ Plotly charts, including portfolio allocation views
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
