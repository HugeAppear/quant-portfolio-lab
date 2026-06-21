"""Plotly charts for the v0.1 backtest result page.

Provides the three required visuals: cumulative return vs benchmark, drawdown,
and an annual return table. Functions return Plotly ``Figure`` objects so they
can be shown in a notebook, embedded in Streamlit, or exported to HTML.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..backtest.metrics import annual_returns, drawdown_series


def _rebased(series: pd.Series, base: float = 1.0) -> pd.Series:
    series = series.sort_index().dropna()
    if series.empty:
        return series
    return base * series / series.iloc[0]


def cumulative_return_chart(
    equity: pd.Series, benchmark: pd.Series | None = None, title: str = "Cumulative Return"
) -> go.Figure:
    """Strategy cumulative return vs benchmark, both rebased to 1.0."""
    fig = go.Figure()
    strat = _rebased(equity)
    fig.add_trace(go.Scatter(x=strat.index, y=strat.values, name="Strategy",
                             line=dict(width=2)))
    if benchmark is not None and not benchmark.empty:
        bench = _rebased(benchmark.reindex(equity.index).ffill())
        fig.add_trace(go.Scatter(x=bench.index, y=bench.values, name="Benchmark",
                                 line=dict(width=1.5, dash="dash")))
    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title="Growth of 1.0",
        hovermode="x unified", template="plotly_white",
    )
    return fig


def drawdown_chart(equity: pd.Series, title: str = "Drawdown") -> go.Figure:
    """Underwater (drawdown) curve."""
    dd = drawdown_series(equity)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values, name="Drawdown", fill="tozeroy",
        line=dict(width=1, color="crimson"),
    ))
    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title="Drawdown",
        yaxis_tickformat=".0%", template="plotly_white",
    )
    return fig


def annual_return_table(
    equity: pd.Series, benchmark: pd.Series | None = None
) -> go.Figure:
    """Annual return table (strategy and, optionally, benchmark)."""
    strat = annual_returns(equity)
    years = [str(y) for y in strat.index]
    cells = [years, [f"{v:.2%}" for v in strat.values]]
    header = ["Year", "Strategy"]
    if benchmark is not None and not benchmark.empty:
        bench_annual = annual_returns(benchmark.reindex(equity.index).ffill())
        bench_annual = bench_annual.reindex(strat.index)
        cells.append([f"{v:.2%}" if pd.notna(v) else "—" for v in bench_annual.values])
        header.append("Benchmark")
    fig = go.Figure(data=[go.Table(
        header=dict(values=header, fill_color="#2b3e50", font=dict(color="white")),
        cells=dict(values=cells, align="center"),
    )])
    fig.update_layout(title="Annual Returns", template="plotly_white")
    return fig
