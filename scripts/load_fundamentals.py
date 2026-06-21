#!/usr/bin/env python3
"""Load fundamentals (EPS/BPS) and build point-in-time factor snapshots.

Primary source : pykrx ``get_market_fundamental`` (PER, PBR, EPS, BPS, DIV).
Fallback       : synthetic data, so this script always runs offline.

Note on point-in-time data: pykrx exposes trailing fundamentals as of a trading
date. We snapshot them and set ``report_date`` to the snapshot date, so the
backtester's ``report_date <= rebalance_date`` rule still applies. For a research
v0.1 this is a reasonable approximation; a stricter pipeline would map to actual
filing dates.

Examples
--------
    python scripts/load_fundamentals.py --start 2018-01-01 --end 2024-12-31
    python scripts/load_fundamentals.py --synthetic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_portfolio_lab.data.db import DEFAULT_DB_PATH, get_connection, init_schema
from quant_portfolio_lab.data.loaders import (
    read_price_panel,
    write_factor_snapshots,
    write_fundamentals,
)
from quant_portfolio_lab.data.synthetic import make_synthetic_market
from quant_portfolio_lab.factors.valuation import build_factor_snapshots

FALLBACK_SYMBOLS = ["005930", "000660", "035720", "005380", "051910", "035420"]


def _symbol_to_asset_id(symbol: str) -> int:
    return int("9" + "".join(ch for ch in symbol if ch.isdigit())[:6].zfill(6))


def _normalize_symbols(symbols) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        symbol = "".join(ch for ch in str(raw) if ch.isdigit())[:6].zfill(6)
        if len(symbol) == 6 and symbol not in seen:
            out.append(symbol)
            seen.add(symbol)
    return out


def symbols_from_assets_table(con, market: str) -> list[str]:
    """Use the same universe that load_prices.py already wrote to assets."""
    rows = con.execute(
        """
        SELECT symbol
        FROM assets
        WHERE data_source = 'pykrx'
          AND asset_type = 'EQUITY'
          AND country = 'KR'
          AND exchange = 'KRX'
          AND (market_segment = ? OR market_segment IS NULL)
        ORDER BY symbol
        """,
        [market],
    ).fetchall()
    return _normalize_symbols(row[0] for row in rows)


def fetch_fundamentals_pykrx(symbols, start, end, freq_days: int = 63,
                             market: str = "KOSPI") -> pd.DataFrame:
    """Sample pykrx fundamentals on a quarterly-ish grid and stack into long form."""
    from pykrx import stock

    grid = pd.bdate_range(start, end, freq=f"{freq_days}D")
    rows = []
    symbols = set(_normalize_symbols(symbols))
    for as_of in grid:
        d = as_of.strftime("%Y%m%d")
        try:
            snap = stock.get_market_fundamental(d, market=market)
        except Exception:  # noqa: BLE001
            continue
        if snap is None or snap.empty:
            continue
        for symbol in symbols:
            if symbol not in snap.index:
                continue
            r = snap.loc[symbol]
            rows.append({
                "asset_id": _symbol_to_asset_id(symbol),
                "fiscal_period": as_of.strftime("%Y-%m-%d"),
                "report_date": as_of.date(),
                "eps": float(r.get("EPS", float("nan"))),
                "bps": float(r.get("BPS", float("nan"))),
                "net_income": None,
                "total_equity": None,
                "shares_outstanding": None,
                "source": "pykrx",
            })
    return pd.DataFrame(rows)


def build_and_write_factor_snapshots(con, fundamentals: pd.DataFrame) -> int:
    """Build factor snapshots on each fundamental as-of date and persist them."""
    panel = read_price_panel(con)
    if panel.empty or fundamentals.empty:
        return 0
    panel.index = pd.DatetimeIndex(panel.index)
    frames = []
    for as_of in sorted(pd.to_datetime(fundamentals["report_date"]).unique()):
        frames.append(build_factor_snapshots(panel, fundamentals, as_of))
    snapshots = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return write_factor_snapshots(con, snapshots)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load fundamentals into DuckDB")
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="Explicit KRX symbols. If omitted, use symbols already in assets.")
    parser.add_argument("--market", default="KOSPI", choices=["KOSPI", "KOSDAQ", "KONEX", "ALL"])
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    con = get_connection(args.db)
    init_schema(con)

    if args.symbols:
        symbols = _normalize_symbols(args.symbols)
        print(f"[load_fundamentals] using {len(symbols)} explicit symbols")
    else:
        symbols = symbols_from_assets_table(con, args.market)
        if symbols:
            print(f"[load_fundamentals] using {len(symbols)} symbols from assets table")
        else:
            symbols = FALLBACK_SYMBOLS
            print("[load_fundamentals] assets table empty; using fallback symbols")

    fundamentals = None
    if not args.synthetic:
        try:
            fundamentals = fetch_fundamentals_pykrx(
                symbols, args.start, args.end, market=args.market
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[load_fundamentals] live source unavailable ({exc}); using synthetic.")
            fundamentals = None

    if fundamentals is None or fundamentals.empty:
        market = make_synthetic_market(start=args.start, end=args.end)
        fundamentals = market.fundamentals
        # Ensure prices exist so factor snapshots can be built offline too.
        from quant_portfolio_lab.data.loaders import persist_market
        persist_market(con, market)

    n_fnd = write_fundamentals(con, fundamentals)
    n_factors = build_and_write_factor_snapshots(con, fundamentals)
    con.close()

    print(f"[load_fundamentals] wrote {n_fnd} fundamental rows, "
          f"{n_factors} factor snapshots -> {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
