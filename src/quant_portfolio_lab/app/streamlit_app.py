"""Streamlit prototype -- backtest result and portfolio configuration page.

Run with:  ``streamlit run src/quant_portfolio_lab/app/streamlit_app.py``

Uses synthetic data by default so it runs offline. The app now supports the
original valuation strategies plus advanced composite strategies and includes
allocation visualizations for the resulting portfolio.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

try:
    import streamlit as st
except ImportError:  # pragma: no cover - app is optional
    raise SystemExit("Streamlit is not installed. Install with: pip install '.[app]'")

from quant_portfolio_lab.backtest.cost_model import CostModel
from quant_portfolio_lab.backtest.engine import BacktestConfig, BacktestEngine
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


DEFAULT_MANUAL_PORTFOLIO = pd.DataFrame(
    [
        {
            "asset_id": 1,
            "symbol": "SP500_PROXY",
            "name": "S&P 500",
            "asset_class": "Equity",
            "weight_pct": 50.0,
        },
        {
            "asset_id": 2,
            "symbol": "BOND_PROXY",
            "name": "Bond",
            "asset_class": "Fixed Income",
            "weight_pct": 50.0,
        }
    ]
)


@st.cache_data(show_spinner=False)
def _load_synthetic():
    market = make_synthetic_market()
    panel = market.prices.pivot(index="date", columns="asset_id", values="close")
    bench = market.benchmark.set_index("date")["close"]
    return panel, market.fundamentals, bench, market.assets


def _run_strategy(
    panel,
    fundamentals,
    bench,
    strategy,
    top_n,
    weighting,
    rebalance,
    fee,
    tax,
    slippage,
):
    cfg = BacktestConfig(
        rebalance_mode=rebalance,
        top_n=top_n,
        benchmark_id="KOSPI",
        weighting=weighting,
    )
    cost_model = CostModel(fee_rate=fee, tax_rate=tax, slippage_rate=slippage)

    if strategy in BASIC_STRATEGIES:
        cfg.factor = BASIC_STRATEGIES[strategy]
        return BacktestEngine(
            panel,
            cost_model,
            fundamentals=fundamentals,
            benchmark=bench,
            config=cfg,
        ).run()

    if strategy in ADVANCED_STRATEGY_NAMES:
        spec = make_strategy_spec(strategy, top_n=top_n, weighting=weighting)
        return BacktestEngine(
            panel,
            cost_model,
            target_func=lambda d: weights_for_date(panel, fundamentals, d, spec),
            benchmark=bench,
            config=cfg,
        ).run()

    raise ValueError(f"unknown strategy {strategy!r}")


def _validate_manual_portfolio(config: pd.DataFrame) -> list[str]:
    errors: list[str] = []

    required = {"asset_id", "symbol", "name", "asset_class", "weight_pct"}
    missing = required.difference(config.columns)
    if missing:
        errors.append(f"Missing required columns: {sorted(missing)}")
        return errors
    
    if config.empty:
        errors.append("Portfolio configuration is empty.")
        return errors
    
    if config["asset_id"].duplicated().any():
        errors.append("Duplicate asset_id values are not allowed.")

    if config["weight_pct"].isna().any():
        errors.append("All rows must have a weight.")
        
    if (config["weight_pct"] < 0).any():
        errors.append("Negative weights are not supported in the MVP.")
        
    total_weight = float(config["weight_pct"].sum())
    if abs(total_weight - 100.0) > 1e-6:
        errors.append(f"Weights must sum to 100%. Current total is {total_weight:.2f}%.")
        
    return errors


def _allocation_bar_chart(config: pd.DataFrame) -> go.Figure:
    frame = config.copy()
    frame["label"] = frame["name"].fillna(frame["symbol"]).astype(str)
    frame = frame.sort_values("weight_pct", ascending=False)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=frame["label"],
            y=frame["weight_pct"] / 100.0,
            text=[f"{w:.1f}%" for w in frame["weight_pct"]],
            hovertemplate="%{x}<br>Weight=%{y:.2%}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Portfolio Configuration",
        xaxis_title="Asset",
        yaxis_title="Weight",
        yaxis_tickformat=".0%",
        template="plotly_white",
    )
    return fig


def _allocation_donut_chart(config: pd.DataFrame) -> go.Figure:
    frame = config.copy()
    frame["label"] = frame["name"].fillna(frame["symbol"]).astype(str)

    fig = go.Figure()
    fig.add_trace(
        go.Pie(
            labels=frame["label"],
            values=frame["weight_pct"],
            hole=0.45,
            hovertemplate="%{label}<br>Weight=%{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Portfolio Allocation",
        template="plotly_white",
    )
    return fig


def render_manual_portfolio_page() -> pd.DataFrame | None:
    st.subheader("Manual Portfolio Configuration")
    st.caption("Research configuration only · not investment advice")

    edited = st.data_editor(
        DEFAULT_MANUAL_PORTFOLIO,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "asset_id": st.column_config.NumberColumn(
                "Asset ID",
                min_value=1,
                step=1,
                required=True,
            ),
            "symbol": st.column_config.TextColumn(
                "Symbol",
                required=True,
            ),
            "name": st.column_config.TextColumn(
                "Name",
                required=True,
            ),
            "asset_class": st.column_config.SelectboxColumn(
                "Asset Class",
                options=["Equity", "Fixed Income", "Cash", "Commodity", "Other"],
                required=True,
            ),
            "weight_pct": st.column_config.NumberColumn(
                "Weight %",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
                format="%.2f",
                required=True,
            ),
        },
    )

    errors = _validate_manual_portfolio(edited)
    if errors:
        for error in errors:
            st.error(error)
        return None

    st.success("Portfolio configuration is valid.")

    display = edited.copy()
    display["weight"] = display["weight_pct"] / 100.0

    st.markdown("### Current allocation")
    for row in display.sort_values("weight", ascending=False).to_dict("records"):
        st.write(f"- {row['weight']:.1%} {row['name']}")

    c1, c2 = st.columns(2)
    c1.plotly_chart(_allocation_bar_chart(display), use_container_width=True)
    c2.plotly_chart(_allocation_donut_chart(display), use_container_width=True)

    st.dataframe(display, use_container_width=True)

    return display


def main() -> None:
    st.set_page_config(page_title="Quant Portfolio Lab", layout="wide")
    
    with st.sidebar:
        mode = st.radio(
            "App mode",
            ["Strategy Backtest", "Manual Portfolio"],
            index=0,
        )
        
    if mode == "Manual Portfolio":
        st.title("Quant Portfolio Lab — Manual Portfolio")
        st.caption("research only · not investment advice")
        
        manual_config = render_manual_portfolio_page()
        
        # Later, this is where you can connect manual_config to BacktestEngine.
        # For now, the manual page shows editable allocation + charts.
        st.stop()
    
    st.title("Quant Portfolio Lab — Backtest Result")
    st.caption("research only · not investment advice")

    with st.sidebar:
        st.header("Strategy")
        strategy = st.selectbox("Strategy", list(ALL_STRATEGY_NAMES), index=0)
        rebalance = st.selectbox("Rebalance", ["1Y", "6M"], index=0)
        top_n = st.slider("Top N", 5, 50, 20, step=5)
        weighting = st.selectbox("Weighting", list(SUPPORTED_WEIGHTINGS), index=0)
        fee = st.number_input("Fee per side", value=0.001, format="%.4f")
        tax = st.number_input("Sell tax", value=0.0020, format="%.4f")
        slippage = st.number_input("Slippage", value=0.002, format="%.4f")

    panel, fundamentals, bench, assets = _load_synthetic()
    result = _run_strategy(
        panel,
        fundamentals,
        bench,
        strategy,
        top_n,
        weighting,
        rebalance,
        fee,
        tax,
        slippage,
    )
    m = result.metrics

    cols = st.columns(5)
    cols[0].metric("CAGR", f"{m.get('cagr', float('nan')):.2%}")
    cols[1].metric("Volatility", f"{m.get('volatility', float('nan')):.2%}")
    cols[2].metric("Max Drawdown", f"{m.get('max_drawdown', float('nan')):.2%}")
    cols[3].metric("Sharpe", f"{m.get('sharpe', float('nan')):.2f}")
    cols[4].metric("Avg Turnover", f"{result.turnover:.2%}")

    st.plotly_chart(
        cumulative_return_chart(result.equity_curve, result.benchmark),
        use_container_width=True,
    )
    
    c1, c2 = st.columns([2, 1])
    c1.plotly_chart(drawdown_chart(result.equity_curve), use_container_width=True)
    c2.plotly_chart(
        annual_return_table(result.equity_curve, result.benchmark),
        use_container_width=True,
    )

    st.subheader("Portfolio configuration")
    c3, c4 = st.columns([3, 2])
    c3.plotly_chart(
        portfolio_weight_bar(result.positions, assets=assets), 
        use_container_width=True,
    )
    c4.plotly_chart(
        portfolio_weight_treemap(result.positions, assets=assets),
        use_container_width=True,
    )
    st.plotly_chart(
        portfolio_weight_heatmap(result.positions, assets=assets),
        use_container_width=True,
    )

    st.subheader("Final holdings")
    if not result.positions.empty:
        last_date = result.positions["date"].max()
        final = result.positions[result.positions["date"] == last_date].sort_values(
            "weight", ascending=False
        )
        final = final.merge(
            assets[["asset_id", "symbol", "name"]], 
            on="asset_id", 
            how="left",
        )
        st.dataframe(final, use_container_width=True)

    st.subheader("Trade history")
    st.dataframe(result.trades, use_container_width=True)


if __name__ == "__main__":
    main()
