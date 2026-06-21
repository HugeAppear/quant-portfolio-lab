"""Factor calculation tests.

Covers Step 9 Test 5 (missing EPS/BPS excluded) and Test 6 (no use of future
financial statements), plus the PER/PBR definitions and sign-exclusion rules.
"""

import math

import numpy as np
import pandas as pd
import pytest

from quant_portfolio_lab.factors.valuation import (
    build_factor_snapshots,
    compute_pbr,
    compute_per,
    rank_by_factor,
    select_universe,
)


# --------------------------------------------------------------------------- #
# PER / PBR definitions and sign exclusions
# --------------------------------------------------------------------------- #
def test_per_definition():
    assert compute_per(12_000, 1_000) == pytest.approx(12.0)


def test_pbr_definition():
    assert compute_pbr(20_000, 10_000) == pytest.approx(2.0)


def test_per_excludes_non_positive_eps():
    assert math.isnan(compute_per(10_000, 0))
    assert math.isnan(compute_per(10_000, -50))


def test_pbr_excludes_non_positive_bps():
    assert math.isnan(compute_pbr(10_000, 0))
    assert math.isnan(compute_pbr(10_000, -100))


def test_missing_inputs_return_nan():
    assert math.isnan(compute_per(10_000, np.nan))
    assert math.isnan(compute_pbr(np.nan, 1_000))


# --------------------------------------------------------------------------- #
# Step 9 -- Test 5: missing EPS/BPS excluded from ranking
# --------------------------------------------------------------------------- #
def test_missing_fundamentals_excluded_from_ranking():
    dates = pd.bdate_range("2021-01-01", periods=10)
    panel = pd.DataFrame(
        {1: 10_000.0, 2: 20_000.0, 3: 30_000.0}, index=dates
    )

    fundamentals = pd.DataFrame([
        {"asset_id": 1, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 5_000.0},
        {"asset_id": 2, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": np.nan, "bps": 8_000.0},      # EPS missing
        {"asset_id": 3, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": 2_000.0, "bps": np.nan},      # BPS missing
    ])

    snap = build_factor_snapshots(panel, fundamentals, dates[-1])
    valid = dict(zip(snap["asset_id"], snap["valid_for_backtest"]))
    assert valid[1] is True or valid[1] == True  # noqa: E712
    assert not valid[2]
    assert not valid[3]

    ranked = rank_by_factor(snap, factor="pbr")
    assert set(ranked["asset_id"]) == {1}


def test_select_universe_drops_invalid_factor_values():
    dates = pd.bdate_range("2021-01-01", periods=5)
    panel = pd.DataFrame({1: 10_000.0, 2: 10_000.0}, index=dates)
    fundamentals = pd.DataFrame([
        {"asset_id": 1, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 5_000.0},
        {"asset_id": 2, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": -10.0, "bps": -5.0},          # non-positive -> NaN factors
    ])
    snap = build_factor_snapshots(panel, fundamentals, dates[-1])
    assert set(select_universe(snap, "per")["asset_id"]) == {1}
    assert set(select_universe(snap, "pbr")["asset_id"]) == {1}


# --------------------------------------------------------------------------- #
# Step 9 -- Test 6: do not use future financial statements
# --------------------------------------------------------------------------- #
def test_point_in_time_ignores_future_reports():
    dates = pd.bdate_range("2018-01-01", "2024-12-31")
    panel = pd.DataFrame({1: 50_000.0}, index=dates)

    fundamentals = pd.DataFrame([
        # Visible at the 2022 rebalance.
        {"asset_id": 1, "fiscal_period": "2019A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 10_000.0},
        # Released AFTER the 2022 rebalance -> must not be used.
        {"asset_id": 1, "fiscal_period": "2024A", "report_date": "2025-03-31",
         "eps": 9_999.0, "bps": 99_999.0},
    ])

    as_of = pd.Timestamp("2022-01-03")
    snap = build_factor_snapshots(panel, fundamentals, as_of)
    row = snap.iloc[0]
    assert row["eps"] == pytest.approx(1_000.0)
    assert row["bps"] == pytest.approx(10_000.0)
    assert row["per"] == pytest.approx(50_000.0 / 1_000.0)
    assert bool(row["valid_for_backtest"]) is True


def test_no_visible_report_marks_invalid():
    dates = pd.bdate_range("2018-01-01", periods=30)
    panel = pd.DataFrame({1: 50_000.0}, index=dates)
    fundamentals = pd.DataFrame([
        {"asset_id": 1, "fiscal_period": "2019A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 10_000.0},
    ])
    # as_of is BEFORE the only report -> nothing visible point-in-time.
    snap = build_factor_snapshots(panel, fundamentals, dates[0])
    row = snap.iloc[0]
    assert math.isnan(row["eps"])
    assert math.isnan(row["bps"])
    assert bool(row["valid_for_backtest"]) is False


def test_ranking_orders_lowest_pbr_first():
    dates = pd.bdate_range("2021-01-01", periods=5)
    panel = pd.DataFrame({1: 10_000.0, 2: 10_000.0, 3: 10_000.0}, index=dates)
    fundamentals = pd.DataFrame([
        {"asset_id": 1, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 2_000.0},   # pbr = 5.0
        {"asset_id": 2, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 10_000.0},  # pbr = 1.0  <- lowest
        {"asset_id": 3, "fiscal_period": "2020A", "report_date": "2020-03-31",
         "eps": 1_000.0, "bps": 5_000.0},   # pbr = 2.0
    ])
    snap = build_factor_snapshots(panel, fundamentals, dates[-1])
    ranked = rank_by_factor(snap, factor="pbr", ascending=True)
    assert list(ranked["asset_id"]) == [2, 3, 1]
    assert list(ranked["rank"]) == [1, 2, 3]
