"""Persist and read market data to/from DuckDB.

These helpers are deliberately thin: they take/return pandas DataFrames using the
same column conventions as the synthetic generator and the real source loaders.
The backtest engine itself consumes plain DataFrames, so it never depends on a
live database connection.
"""

from __future__ import annotations

try:
    import duckdb
except ImportError:  # pragma: no cover - optional when only synthetic data is used
    duckdb = None

import pandas as pd

# Columns persisted per table (extra DataFrame columns are ignored).
_ASSET_COLS = [
    "asset_id", "symbol", "isin", "name", "asset_type", "country", "exchange",
    "currency", "market_segment", "listing_date", "delisting_date", "data_source",
]
_PRICE_COLS = [
    "asset_id", "date", "open", "high", "low", "close", "adjusted_close",
    "volume", "value_traded", "source",
]
_FUNDAMENTAL_COLS = [
    "asset_id", "fiscal_period", "report_date", "eps", "bps", "net_income",
    "total_equity", "shares_outstanding", "source",
]
_FACTOR_COLS = [
    "asset_id", "as_of_date", "price", "eps", "bps", "per", "pbr",
    "valid_for_backtest",
]
_BENCHMARK_COLS = ["benchmark_id", "date", "close", "source"]


def _replace_into(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame,
                  cols: list[str]) -> int:
    """Insert ``df[cols]`` into ``table``, replacing rows with matching keys.

    Uses DuckDB's ability to query a registered pandas frame. Existing rows that
    collide on the primary key are deleted first (a simple idempotent upsert).
    """
    if df is None or df.empty:
        return 0
    frame = df.copy()
    for col in cols:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[cols]
    con.register("_staging", frame)
    try:
        con.execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM _staging")
    except Exception:
        # Tables without a PK (e.g. backtest_trades) -> plain append.
        con.execute(f"INSERT INTO {table} SELECT * FROM _staging")
    finally:
        con.unregister("_staging")
    return len(frame)


def write_assets(con, df: pd.DataFrame) -> int:
    return _replace_into(con, "assets", df, _ASSET_COLS)


def write_prices(con, df: pd.DataFrame) -> int:
    return _replace_into(con, "price_bars", df, _PRICE_COLS)


def write_fundamentals(con, df: pd.DataFrame) -> int:
    return _replace_into(con, "fundamental_snapshots", df, _FUNDAMENTAL_COLS)


def write_factor_snapshots(con, df: pd.DataFrame) -> int:
    return _replace_into(con, "factor_snapshots", df, _FACTOR_COLS)


def write_benchmark(con, df: pd.DataFrame) -> int:
    return _replace_into(con, "benchmark_prices", df, _BENCHMARK_COLS)


def persist_market(con, market) -> dict[str, int]:
    """Write a :class:`SyntheticMarket` (or equivalent frames) to DuckDB."""
    return {
        "assets": write_assets(con, market.assets),
        "prices": write_prices(con, market.prices),
        "fundamentals": write_fundamentals(con, market.fundamentals),
        "benchmark": write_benchmark(con, market.benchmark),
    }


def read_assets(con) -> pd.DataFrame:
    """Return asset metadata ordered by ``asset_id``."""
    try:
        return con.execute("SELECT * FROM assets ORDER BY asset_id").df()
    except Exception:
        return pd.DataFrame()


def read_fundamentals(con, asset_ids: list[int] | None = None) -> pd.DataFrame:
    """Return fundamental snapshots, optionally restricted to ``asset_ids``."""
    where = ""
    params: list[int] = []
    if asset_ids:
        placeholders = ", ".join("?" for _ in asset_ids)
        where = f"WHERE asset_id IN ({placeholders})"
        params = [int(a) for a in asset_ids]
    return con.execute(
        f"SELECT * FROM fundamental_snapshots {where} ORDER BY asset_id, report_date",
        params,
    ).df()


def read_price_panel(con, asset_ids: list[int] | None = None) -> pd.DataFrame:
    """Return a wide close-price panel indexed by date, columns = asset_id."""
    where = ""
    if asset_ids:
        ids = ", ".join(str(int(a)) for a in asset_ids)
        where = f"WHERE asset_id IN ({ids})"
    df = con.execute(
        f"SELECT date, asset_id, close FROM price_bars {where} ORDER BY date"
    ).df()
    if df.empty:
        return df
    return df.pivot(index="date", columns="asset_id", values="close")


def read_benchmark(con, benchmark_id: str) -> pd.Series:
    df = con.execute(
        "SELECT date, close FROM benchmark_prices WHERE benchmark_id = ? ORDER BY date",
        [benchmark_id],
    ).df()
    return df.set_index("date")["close"] if not df.empty else pd.Series(dtype=float)
