"""Quant Portfolio Lab -- a personal quant research platform (v0.1).

The package is organised into focused sub-modules:

- ``data``           : DuckDB schema + load/query helpers and synthetic data.
- ``factors``        : PER/PBR valuation factors, exclusion + point-in-time rules.
- ``portfolio``      : portfolio construction (top-N selection, equal weight).
- ``backtest``       : rebalance calendar, transaction-cost model, engine, metrics.
- ``visualization``  : Plotly charts for the backtest result page.
- ``app``            : Streamlit prototype (optional).

v0.1 goal is **correctness**, not optimisation. See ``specs/`` for the policy.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
