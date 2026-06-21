"""Streamlit prototype -- the single v0.1 "Backtest result page".

Run with:  ``streamlit run src/quant_portfolio_lab/app/streamlit_app.py``

Shows cumulative return vs benchmark, drawdown, the annual return table, the
headline metrics (CAGR, volatility, max drawdown, Sharpe, turnover), final
holdings, and trade history. Uses synthetic data by default so it runs offline.
"""

from __future__ import annotations

import pandas as pd

try:
    import streamlit as st
except ImportError:  # pragma: no cover - app is optional
    raise SystemExit("Streamlit is not installed. Install with: pip install '.[app]'")

from quant_portfolio_lab.backtest.cost_model import CostModel
from quant_portfolio_lab.backtest.engine import BacktestConfig, BacktestEngine
from quant_portfolio_lab.data.synthetic import make_synthetic_market
from quant_portfolio_lab.visualization.charts import (
    annual_return_table,
    cumulative_return_chart,
    drawdown_chart,
)


@st.cache_data(show_spinner=False)
def _load_synthetic():
    market = make_synthetic_market()
    panel = market.prices.pivot(index="date", columns="asset_id", values="close")
    bench = market.benchmark.set_index("date")["close"]
    return panel, market.fundamentals, bench


def main() -> None:
    st.set_page_config(page_title="Quant Portfolio Lab", layout="wide")
    st.title("Quant Portfolio Lab — Backtest Result")
    st.caption("v0.1 · research only · not investment advice")

    with st.sidebar:
        st.header("Strategy")
        factor = st.selectbox("Factor", ["pbr", "per"], index=0)
        rebalance = st.selectbox("Rebalance", ["1Y", "6M"], index=0)
        top_n = st.slider("Top N", 5, 30, 20, step=5)
        fee = st.number_input("Fee per side", value=0.001, format="%.4f")
        tax = st.number_input("Sell tax", value=0.0020, format="%.4f")
        slippage = st.number_input("Slippage", value=0.002, format="%.4f")

    panel, fundamentals, bench = _load_synthetic()
    engine = BacktestEngine(
        panel,
        CostModel(fee_rate=fee, tax_rate=tax, slippage_rate=slippage),
        fundamentals=fundamentals,
        benchmark=bench,
        config=BacktestConfig(
            rebalance_mode=rebalance, top_n=top_n, factor=factor,
            benchmark_id="KOSPI",
        ),
    )
    result = engine.run()
    m = result.metrics

    cols = st.columns(5)
    cols[0].metric("CAGR", f"{m.get('cagr', float('nan')):.2%}")
    cols[1].metric("Volatility", f"{m.get('volatility', float('nan')):.2%}")
    cols[2].metric("Max Drawdown", f"{m.get('max_drawdown', float('nan')):.2%}")
    cols[3].metric("Sharpe", f"{m.get('sharpe', float('nan')):.2f}")
    cols[4].metric("Avg Turnover", f"{result.turnover:.2%}")

    st.plotly_chart(cumulative_return_chart(result.equity_curve, result.benchmark),
                    use_container_width=True)
    c1, c2 = st.columns([2, 1])
    c1.plotly_chart(drawdown_chart(result.equity_curve), use_container_width=True)
    c2.plotly_chart(annual_return_table(result.equity_curve, result.benchmark),
                    use_container_width=True)

    st.subheader("Final holdings")
    if not result.positions.empty:
        last_date = result.positions["date"].max()
        st.dataframe(result.positions[result.positions["date"] == last_date]
                     .sort_values("weight", ascending=False), use_container_width=True)

    st.subheader("Trade history")
    st.dataframe(result.trades, use_container_width=True)


if __name__ == "__main__":
    main()
