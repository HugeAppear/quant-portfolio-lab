#!/usr/bin/env python3
"""Load daily price bars and benchmark closes into DuckDB.

Primary source : pykrx (KRX listed equities / ETFs).
Benchmark      : FinanceDataReader (KOSPI = symbol ``KS11``).
Fallback       : synthetic data, so this script always runs offline.

Examples
--------
    # Load the 100 largest KOSPI common stocks at the beginning of the backtest.
    python scripts/load_prices.py --start 2018-01-01 --end 2024-12-31 --universe-size 100

    # Load an explicit list.
    python scripts/load_prices.py --symbols 005930 000660 035720

    # Load synthetic data only.
    python scripts/load_prices.py --synthetic
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

# Allow running the script directly from a checkout (no install required).
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_portfolio_lab.data.db import DEFAULT_DB_PATH, get_connection, init_schema
from quant_portfolio_lab.data.loaders import write_assets, write_benchmark, write_prices
from quant_portfolio_lab.data.synthetic import make_synthetic_market

# Manual fallback universe used only if automatic KRX universe discovery fails.
FALLBACK_SYMBOLS = ["005930", "000660", "035720", "005380", "051910", "035420"]
BENCHMARK_SYMBOL = "KS11"  # KOSPI on FinanceDataReader
PREFERRED_SHARE_RE = re.compile(r"(\d+우[A-Z]?$|우[A-Z]?$|우$)")


def _symbol_to_asset_id(symbol: str) -> int:
    """Stable integer asset_id derived from the 6-digit KRX code."""
    return int("9" + "".join(ch for ch in symbol if ch.isdigit())[:6].zfill(6))


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    """Return unique 6-digit KRX symbols, preserving input order."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        symbol = "".join(ch for ch in str(raw) if ch.isdigit())[:6].zfill(6)
        if len(symbol) == 6 and symbol not in seen:
            out.append(symbol)
            seen.add(symbol)
    return out


def _yyyymmdd(date_like: str) -> str:
    return pd.Timestamp(date_like).strftime("%Y%m%d")


def _date_candidates(as_of: str, lookback_days: int = 14) -> list[str]:
    """Try as_of, then prior calendar days, to survive weekends/holidays."""
    anchor = pd.Timestamp(as_of)
    return [
        (anchor - pd.Timedelta(days=i)).strftime("%Y%m%d")
        for i in range(lookback_days + 1)
    ]


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {str(col).lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def _fetch_market_cap_snapshot(stock, date_c: str, market: str) -> pd.DataFrame:
    """Fetch one market-cap snapshot while tolerating pykrx API variants."""
    attempts = [
        lambda: stock.get_market_cap(date_c, market=market),
        lambda: stock.get_market_cap_by_ticker(date_c, market=market),
        lambda: stock.get_market_cap(date_c),
    ]
    last_exc: Exception | None = None
    for attempt in attempts:
        try:
            df = attempt()
        except (TypeError, AttributeError) as exc:
            last_exc = exc
            continue
        if df is not None and not df.empty:
            return df
    if last_exc is not None:
        raise last_exc
    return pd.DataFrame()


def _looks_preferred_share(name: str) -> bool:
    """Best-effort Korean preferred-share name filter, e.g. 삼성전자우, 현대차2우B."""
    return bool(PREFERRED_SHARE_RE.search(str(name)))


def resolve_symbols_pykrx(
    *,
    market: str,
    universe_size: int,
    universe_asof: str,
    include_preferred: bool,
) -> list[str]:
    """Resolve a KRX universe by market cap.

    universe_size <= 0 means all symbols returned by the market-cap snapshot.
    Preferred shares are excluded by default because the project universe is
    intended to be common equity.
    """
    from pykrx import stock

    limit = None if universe_size <= 0 else int(universe_size)
    cap = pd.DataFrame()
    used_date = None

    for date_c in _date_candidates(universe_asof):
        try:
            cap = _fetch_market_cap_snapshot(stock, date_c, market)
        except Exception:
            continue
        if cap is not None and not cap.empty:
            used_date = date_c
            break

    if cap is None or cap.empty:
        # Last resort: use ticker list, unsorted. This is less desirable than
        # market-cap ranking but keeps the loader usable.
        for date_c in _date_candidates(universe_asof):
            try:
                tickers = stock.get_market_ticker_list(date_c, market=market)
            except Exception:
                continue
            tickers = _normalize_symbols(tickers)
            if tickers:
                print(
                    f"[load_prices] market-cap snapshot unavailable; "
                    f"using {len(tickers)} tickers from get_market_ticker_list({date_c})."
                )
                return tickers if limit is None else tickers[:limit]
        print("[load_prices] KRX universe discovery failed; using fallback symbols.")
        return FALLBACK_SYMBOLS

    cap = cap.copy()
    cap["symbol"] = _normalize_symbols(cap.index.astype(str))

    cap_col = _first_existing_column(cap, ["시가총액", "market_cap", "marcap", "Marcap"])
    if cap_col is not None:
        cap[cap_col] = pd.to_numeric(cap[cap_col], errors="coerce")
        cap = cap.sort_values(cap_col, ascending=False, kind="mergesort")

    selected: list[str] = []
    for symbol in cap["symbol"].dropna().tolist():
        try:
            name = stock.get_market_ticker_name(symbol) or ""
        except Exception:
            name = ""
        if not include_preferred and _looks_preferred_share(name):
            continue
        selected.append(symbol)
        if limit is not None and len(selected) >= limit:
            break

    if not selected:
        selected = FALLBACK_SYMBOLS

    size_label = "all" if limit is None else str(limit)
    print(
        f"[load_prices] resolved {len(selected)} {market} symbols "
        f"by market cap as of {used_date} (requested {size_label})."
    )
    return selected


def fetch_prices_pykrx(
    symbols: list[str],
    start: str,
    end: str,
    *,
    market: str = "KOSPI",
    sleep_seconds: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch OHLCV via pykrx. Returns (assets_df, prices_df) in long form."""
    from pykrx import stock  # imported lazily so the dep is optional

    start_c = _yyyymmdd(start)
    end_c = _yyyymmdd(end)

    asset_rows, price_frames = [], []
    total = len(symbols)
    for i, symbol in enumerate(symbols, start=1):
        try:
            df = stock.get_market_ohlcv(start_c, end_c, symbol)
        except Exception as exc:
            print(f"[load_prices] skipped {symbol}: {exc}")
            continue

        if df is None or df.empty:
            print(f"[load_prices] skipped {symbol}: no OHLCV rows")
            continue

        df = df.rename(columns={
            "시가": "open", "고가": "high", "저가": "low",
            "종가": "close", "거래량": "volume", "거래대금": "value_traded",
        })
        df = df.reset_index().rename(columns={"날짜": "date", "index": "date"})
        df["date"] = pd.to_datetime(df["date"])
        asset_id = _symbol_to_asset_id(symbol)
        df["asset_id"] = asset_id
        df["adjusted_close"] = df["close"]
        df["source"] = "pykrx"
        if "value_traded" not in df.columns:
            df["value_traded"] = df["close"] * df["volume"]
        price_frames.append(df)

        name = stock.get_market_ticker_name(symbol)
        asset_rows.append({
            "asset_id": asset_id, "symbol": symbol, "name": name,
            "asset_type": "EQUITY", "country": "KR", "exchange": "KRX",
            "currency": "KRW", "market_segment": market, "data_source": "pykrx",
        })

        if i % 10 == 0 or i == total:
            print(f"[load_prices] fetched {i}/{total} symbols")
        if sleep_seconds > 0 and i < total:
            time.sleep(float(sleep_seconds))

    prices = pd.concat(price_frames, ignore_index=True) if price_frames else pd.DataFrame()
    return pd.DataFrame(asset_rows), prices


def fetch_benchmark_fdr(start: str, end: str, benchmark_id: str = "KOSPI") -> pd.DataFrame:
    """Fetch the KOSPI index via FinanceDataReader."""
    import FinanceDataReader as fdr  # lazy optional import

    df = fdr.DataReader(BENCHMARK_SYMBOL, start, end)
    df = df.reset_index().rename(columns={"Date": "date", "Close": "close"})
    return pd.DataFrame({
        "benchmark_id": benchmark_id,
        "date": pd.to_datetime(df["date"]),
        "close": df["close"].astype(float),
        "source": "FinanceDataReader",
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Load price bars into DuckDB")
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="Explicit KRX symbols. If omitted, build a market-cap universe.")
    parser.add_argument("--market", default="KOSPI", choices=["KOSPI", "KOSDAQ", "KONEX", "ALL"],
                        help="KRX market used for automatic universe discovery.")
    parser.add_argument("--universe-size", type=int, default=100,
                        help="Number of market-cap-ranked symbols to load. Use 0 for all.")
    parser.add_argument("--universe-asof", default=None,
                        help="Date used to choose the market-cap universe. Defaults to --start.")
    parser.add_argument("--include-preferred", action="store_true",
                        help="Include Korean preferred shares in the automatic universe.")
    parser.add_argument("--sleep", type=float, default=0.2,
                        help="Seconds to sleep between pykrx symbol requests.")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--synthetic", action="store_true",
                        help="Skip live sources and load synthetic data.")
    args = parser.parse_args()

    con = get_connection(args.db)
    init_schema(con)

    assets = prices = benchmark = None
    if not args.synthetic:
        try:
            if args.symbols:
                symbols = _normalize_symbols(args.symbols)
                print(f"[load_prices] using {len(symbols)} explicit symbols")
            else:
                symbols = resolve_symbols_pykrx(
                    market=args.market,
                    universe_size=args.universe_size,
                    universe_asof=args.universe_asof or args.start,
                    include_preferred=args.include_preferred,
                )
            assets, prices = fetch_prices_pykrx(
                symbols,
                args.start,
                args.end,
                market=args.market,
                sleep_seconds=args.sleep,
            )
            benchmark = fetch_benchmark_fdr(args.start, args.end)
        except Exception as exc:  # noqa: BLE001 - any failure -> synthetic fallback
            print(f"[load_prices] live source unavailable ({exc}); using synthetic data.")
            assets = prices = benchmark = None

    if prices is None or prices.empty:
        market = make_synthetic_market(start=args.start, end=args.end)
        assets, prices, benchmark = market.assets, market.prices, market.benchmark

    n_assets = write_assets(con, assets)
    n_prices = write_prices(con, prices)
    n_bench = write_benchmark(con, benchmark)
    con.close()

    print(f"[load_prices] wrote {n_assets} assets, {n_prices} price rows, "
          f"{n_bench} benchmark rows -> {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
