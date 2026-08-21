"""Market-input loading shared by the API services.

Mirrors the fallback logic of ``scripts/run_backtest.py``: use the DuckDB
database when it exists and holds prices + fundamentals, otherwise fall back to
the deterministic synthetic market so the GUI always works offline.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..data.db import DEFAULT_DB_PATH, get_connection, init_schema
from ..data.loaders import read_assets, read_benchmark, read_price_panel
from ..data.synthetic import make_synthetic_market

# DuckDB allows one writing process at a time; serialize all connections that
# this API process opens so background runs and request handlers never race.
DB_LOCK = threading.RLock()


@dataclass
class MarketInputs:
    panel: pd.DataFrame          # wide close panel, index=date, cols=asset_id
    fundamentals: pd.DataFrame
    benchmark: pd.Series | None
    assets: pd.DataFrame
    mode: str                    # "duckdb" | "synthetic"


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path is not None else Path(DEFAULT_DB_PATH)


def load_market_inputs(
    benchmark_id: str = "KOSPI",
    *,
    data_mode: str = "auto",
    db_path: str | Path | None = None,
) -> MarketInputs:
    """Return market inputs, preferring DuckDB unless ``data_mode='synthetic'``."""
    path = resolve_db_path(db_path)
    if data_mode != "synthetic" and path.exists():
        with DB_LOCK:
            con = get_connection(path)
            try:
                init_schema(con)
                panel = read_price_panel(con)
                fundamentals = con.execute("SELECT * FROM fundamental_snapshots").df()
                benchmark = read_benchmark(con, benchmark_id)
                assets = read_assets(con)
            finally:
                con.close()
        if not panel.empty and not fundamentals.empty:
            panel.index = pd.DatetimeIndex(panel.index)
            bench = benchmark if not benchmark.empty else None
            if bench is not None:
                bench = bench.copy()
                bench.index = pd.DatetimeIndex(bench.index)
            return MarketInputs(panel, fundamentals, bench, assets, "duckdb")

    market = make_synthetic_market(benchmark_id=benchmark_id)
    panel = market.prices.pivot(index="date", columns="asset_id", values="close")
    panel.index = pd.DatetimeIndex(panel.index)
    bench = market.benchmark.set_index("date")["close"]
    bench.index = pd.DatetimeIndex(bench.index)
    return MarketInputs(panel, market.fundamentals, bench, market.assets, "synthetic")


def slice_by_date(obj, start=None, end=None):
    """Restrict a date-indexed frame/series to ``[start, end]`` (inclusive)."""
    if obj is None or len(obj) == 0:
        return obj
    out = obj.copy()
    out.index = pd.DatetimeIndex(out.index)
    if start:
        out = out.loc[out.index >= pd.Timestamp(start)]
    if end:
        out = out.loc[out.index <= pd.Timestamp(end)]
    return out


def asset_labels(assets: pd.DataFrame) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    """Return ``asset_id -> (symbol, name, market_segment)`` lookup dicts."""
    symbols: dict[int, str] = {}
    names: dict[int, str] = {}
    segments: dict[int, str] = {}
    if assets is not None and not assets.empty:
        for row in assets.itertuples(index=False):
            aid = int(row.asset_id)
            symbols[aid] = str(getattr(row, "symbol", aid) or aid)
            name = getattr(row, "name", None)
            if name is not None and not pd.isna(name):
                names[aid] = str(name)
            seg = getattr(row, "market_segment", None)
            if seg is not None and not pd.isna(seg):
                segments[aid] = str(seg)
    return symbols, names, segments
