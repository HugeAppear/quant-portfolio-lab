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


def _asset_label_map(assets: pd.DataFrame | None = None) -> dict:
    """Return ``asset_id -> display label`` from an optional asset metadata frame."""
    if assets is None or assets.empty or "asset_id" not in assets.columns:
        return {}
    labels = {}
    for row in assets.to_dict("records"):
        asset_id = row.get("asset_id")
        symbol = row.get("symbol")
        name = row.get("name")
        if pd.notna(symbol) and pd.notna(name):
            label = f"{symbol} · {name}"
        elif pd.notna(symbol):
            label = str(symbol)
        elif pd.notna(name):
            label = str(name)
        else:
            label = str(asset_id)
        labels[asset_id] = label
    return labels


def _latest_position_slice(positions: pd.DataFrame, date=None) -> pd.DataFrame:
    if positions is None or positions.empty:
        return pd.DataFrame()
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    if date is None:
        date = frame["date"].max()
    else:
        date = pd.Timestamp(date)
    return frame.loc[frame["date"] == date].copy()


def portfolio_weight_bar(
    positions: pd.DataFrame,
    *,
    date=None,
    assets: pd.DataFrame | None = None,
    top_n: int = 30,
    title: str = "Portfolio Weights",
) -> go.Figure:
    """Bar chart of portfolio weights on one rebalance/position date."""
    frame = _latest_position_slice(positions, date)
    labels = _asset_label_map(assets)
    fig = go.Figure()
    if frame.empty:
        fig.update_layout(title=title, template="plotly_white")
        return fig
    frame = frame.sort_values("weight", ascending=False).head(top_n)
    frame["label"] = frame["asset_id"].map(labels).fillna(frame["asset_id"].astype(str))
    fig.add_trace(
        go.Bar(
            x=frame["label"],
            y=frame["weight"],
            text=[f"{w:.1%}" for w in frame["weight"]],
            hovertemplate="%{x}<br>Weight=%{y:.2%}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{title} · {pd.Timestamp(frame['date'].iloc[0]).date()}",
        xaxis_title="Asset",
        yaxis_title="Weight",
        yaxis_tickformat=".0%",
        template="plotly_white",
    )
    return fig


def portfolio_weight_treemap(
    positions: pd.DataFrame,
    *,
    date=None,
    assets: pd.DataFrame | None = None,
    top_n: int = 50,
    title: str = "Portfolio Allocation Treemap",
) -> go.Figure:
    """Treemap of portfolio weights on one rebalance/position date."""
    frame = _latest_position_slice(positions, date)
    labels = _asset_label_map(assets)
    fig = go.Figure()
    if frame.empty:
        fig.update_layout(title=title, template="plotly_white")
        return fig
    frame = frame.sort_values("weight", ascending=False).head(top_n)
    frame["label"] = frame["asset_id"].map(labels).fillna(frame["asset_id"].astype(str))
    fig.add_trace(
        go.Treemap(
            labels=frame["label"],
            parents=[""] * len(frame),
            values=frame["weight"],
            hovertemplate="%{label}<br>Weight=%{value:.2%}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{title} · {pd.Timestamp(frame['date'].iloc[0]).date()}",
        template="plotly_white",
    )
    return fig


def portfolio_weight_heatmap(
    positions: pd.DataFrame,
    *,
    assets: pd.DataFrame | None = None,
    top_n: int = 30,
    title: str = "Portfolio Weights Over Time",
) -> go.Figure:
    """Heatmap showing how portfolio weights change across rebalance dates."""
    fig = go.Figure()
    if positions is None or positions.empty:
        fig.update_layout(title=title, template="plotly_white")
        return fig

    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    importance = frame.groupby("asset_id")["weight"].max().sort_values(ascending=False)
    keep = importance.head(top_n).index
    frame = frame.loc[frame["asset_id"].isin(keep)]
    pivot = frame.pivot_table(index="asset_id", columns="date", values="weight", fill_value=0.0)
    pivot = pivot.reindex(importance.head(top_n).index)
    labels = _asset_label_map(assets)
    y_labels = [labels.get(asset_id, str(asset_id)) for asset_id in pivot.index]

    fig.add_trace(
        go.Heatmap(
            x=pivot.columns,
            y=y_labels,
            z=pivot.to_numpy(),
            hovertemplate="Date=%{x|%Y-%m-%d}<br>Asset=%{y}<br>Weight=%{z:.2%}<extra></extra>",
            colorbar=dict(title="Weight", tickformat=".0%"),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Asset",
        template="plotly_white",
    )
    return fig


def recommendation_weight_bar(
    recommendations: pd.DataFrame,
    *,
    title: str = "Research Shortlist Target Weights",
) -> go.Figure:
    """Bar chart for a recommendation table produced by recommendation.py."""
    fig = go.Figure()
    if recommendations is None or recommendations.empty:
        fig.update_layout(title=title, template="plotly_white")
        return fig
    frame = recommendations.copy().sort_values("target_weight", ascending=False)
    if "symbol" in frame.columns and "name" in frame.columns:
        frame["label"] = frame.apply(
            lambda row: f"{row['symbol']} · {row['name']}"
            if pd.notna(row.get("symbol")) and pd.notna(row.get("name"))
            else str(row["asset_id"]),
            axis=1,
        )
    else:
        frame["label"] = frame["asset_id"].astype(str)
    fig.add_trace(
        go.Bar(
            x=frame["label"],
            y=frame["target_weight"],
            text=[f"{w:.1%}" for w in frame["target_weight"]],
            hovertemplate="%{x}<br>Target weight=%{y:.2%}<extra></extra>",
        )
    )
    as_of = frame["as_of_date"].iloc[0] if "as_of_date" in frame.columns else "latest"
    fig.update_layout(
        title=f"{title} · {as_of}",
        xaxis_title="Asset",
        yaxis_title="Target Weight",
        yaxis_tickformat=".0%",
        template="plotly_white",
    )
    return fig
