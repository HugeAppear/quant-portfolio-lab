"""Rebalance calendar utilities.

Two rebalancing modes are supported in v0.1 (spec section 5):

- ``"1Y"`` : once per year, on the first trading day of each year.
- ``"6M"`` : twice per year, on the first trading day of June and December.

If a scheduled date is not a trading day, the next available trading day is used
(holiday roll-forward).
"""

from __future__ import annotations

import pandas as pd

VALID_MODES = ("6M", "1Y")


def next_trading_day(target, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:
    """First trading day on or after ``target``; ``None`` if past the calendar."""
    target = pd.Timestamp(target)
    trading_days = pd.DatetimeIndex(trading_days).sort_values()
    pos = trading_days.searchsorted(target, side="left")
    if pos >= len(trading_days):
        return None
    return trading_days[pos]


def generate_rebalance_dates(
    trading_days: pd.DatetimeIndex,
    mode: str = "1Y",
    start=None,
    end=None,
) -> list[pd.Timestamp]:
    """Generate rebalance dates within the trading calendar.

    Each scheduled target date is rolled forward to the next available trading
    day. Duplicate / out-of-range dates are removed.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    trading_days = pd.DatetimeIndex(trading_days).sort_values()
    if len(trading_days) == 0:
        return []

    lo = pd.Timestamp(start) if start is not None else trading_days[0]
    hi = pd.Timestamp(end) if end is not None else trading_days[-1]

    targets: list[pd.Timestamp] = []
    for year in range(lo.year, hi.year + 1):
        if mode == "1Y":
            targets.append(pd.Timestamp(year=year, month=1, day=1))
        else:  # "6M"
            targets.append(pd.Timestamp(year=year, month=6, day=1))
            targets.append(pd.Timestamp(year=year, month=12, day=1))

    rebalance_dates: list[pd.Timestamp] = []
    for target in targets:
        td = next_trading_day(target, trading_days)
        if td is None:
            continue
        if td < lo or td > hi:
            continue
        if td not in rebalance_dates:
            rebalance_dates.append(td)

    return sorted(rebalance_dates)
