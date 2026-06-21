"""Deterministic synthetic market generator.

Used so the engine, scripts, and tests run fully offline (no network / no
pykrx). The generated frames follow the same column conventions as the real
loaders, so downstream code is identical for synthetic and real data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SyntheticMarket:
    """Container of synthetic market frames (same columns as real loaders)."""

    assets: pd.DataFrame        # asset_id, symbol, name, asset_type, ...
    prices: pd.DataFrame        # asset_id, date, open/high/low/close, volume
    fundamentals: pd.DataFrame  # asset_id, fiscal_period, report_date, eps, bps
    benchmark: pd.DataFrame     # benchmark_id, date, close


def make_synthetic_market(
    n_assets: int = 12,
    start: str = "2018-01-01",
    end: str = "2024-12-31",
    benchmark_id: str = "KOSPI",
    seed: int = 7,
) -> SyntheticMarket:
    """Generate a small, reproducible KR-style equity market.

    Each asset gets a geometric-random-walk price series and one fundamental
    snapshot per fiscal year, reported on the following March 31 (so that a
    January rebalance correctly cannot see the just-ended fiscal year).
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    n_days = len(dates)

    asset_rows = []
    price_frames = []
    fundamental_rows = []

    for i in range(n_assets):
        asset_id = 1000 + i
        symbol = f"{5930 + i * 7:06d}"  # pseudo KRX 6-digit code
        base_price = float(rng.uniform(5_000, 120_000))
        drift = rng.normal(0.06, 0.05) / 252.0          # annualised-ish drift
        vol = float(rng.uniform(0.18, 0.45)) / np.sqrt(252.0)

        shocks = rng.normal(drift, vol, size=n_days)
        close = base_price * np.exp(np.cumsum(shocks))
        close = np.round(close, 0)

        intraday = 1.0 + rng.uniform(-0.01, 0.01, size=n_days)
        open_ = np.round(close * intraday, 0)
        high = np.round(np.maximum(open_, close) * (1 + rng.uniform(0, 0.02, n_days)), 0)
        low = np.round(np.minimum(open_, close) * (1 - rng.uniform(0, 0.02, n_days)), 0)
        volume = rng.integers(50_000, 5_000_000, size=n_days).astype(float)

        price_frames.append(
            pd.DataFrame(
                {
                    "asset_id": asset_id,
                    "date": dates,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "adjusted_close": close,
                    "volume": volume,
                    "value_traded": close * volume,
                    "source": "synthetic",
                }
            )
        )

        asset_rows.append(
            {
                "asset_id": asset_id,
                "symbol": symbol,
                "isin": f"KR7{symbol}000",
                "name": f"SynthCo {i + 1}",
                "asset_type": "EQUITY",
                "country": "KR",
                "exchange": "KRX",
                "currency": "KRW",
                "market_segment": "KOSPI" if i % 3 else "KOSDAQ",
                "listing_date": dates[0].date(),
                "delisting_date": None,
                "data_source": "synthetic",
            }
        )

        # One fundamental per fiscal year, reported the following March 31.
        for year in range(dates[0].year, dates[-1].year + 1):
            fy_end = pd.Timestamp(year=year, month=12, day=31)
            report_date = pd.Timestamp(year=year + 1, month=3, day=31)
            # EPS/BPS loosely tied to price level so PER/PBR are sensible.
            ref_price = float(close[min(n_days - 1, max(0, (fy_end - dates[0]).days))])
            eps = round(ref_price / float(rng.uniform(5, 30)), 2)
            bps = round(ref_price / float(rng.uniform(0.5, 3.0)), 2)
            # Inject a couple of "bad" fundamentals to exercise exclusion rules.
            if i == 0 and year == dates[0].year:
                eps = -abs(eps)  # negative earnings -> excluded from low-PER
            if i == 1 and year == dates[0].year:
                bps = 0.0        # zero book value -> excluded from low-PBR
            fundamental_rows.append(
                {
                    "asset_id": asset_id,
                    "fiscal_period": f"{year}A",
                    "report_date": report_date.date(),
                    "eps": eps,
                    "bps": bps,
                    "net_income": eps * 1_000_000,
                    "total_equity": bps * 1_000_000,
                    "shares_outstanding": 1_000_000.0,
                    "source": "synthetic",
                }
            )

    # Benchmark: equal-weighted average of the asset closes, rebased to 2000.
    prices = pd.concat(price_frames, ignore_index=True)
    wide_close = prices.pivot(index="date", columns="asset_id", values="close")
    bench_level = wide_close.mean(axis=1)
    bench_level = 2000.0 * bench_level / bench_level.iloc[0]
    benchmark = pd.DataFrame(
        {
            "benchmark_id": benchmark_id,
            "date": bench_level.index,
            "close": bench_level.to_numpy(),
            "source": "synthetic",
        }
    )

    return SyntheticMarket(
        assets=pd.DataFrame(asset_rows),
        prices=prices,
        fundamentals=pd.DataFrame(fundamental_rows),
        benchmark=benchmark,
    )
