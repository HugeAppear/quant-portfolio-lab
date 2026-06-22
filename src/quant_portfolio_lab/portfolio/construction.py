"""Portfolio construction: top-N selection and weighting schemes.

The original v0.1 implementation supported equal-weighted top-N portfolios.
This module keeps that behavior as the default and adds two reusable weighting
schemes for more advanced strategies:

- ``score``: weights selected names in proportion to a positive signal score.
- ``inverse_vol``: allocates more to lower-volatility names.

The functions intentionally accept plain pandas DataFrames and dictionaries so
they can be reused by the backtest engine, recommendation scripts, notebooks,
and Streamlit app without introducing another dependency layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


SUPPORTED_WEIGHTINGS = ("equal", "score", "inverse_vol")


def select_top_n(ranked: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return the top ``n`` rows of a frame already ranked best-first."""
    if n <= 0:
        raise ValueError("n must be positive")
    return ranked.head(n).copy()


def _finite_positive(values: Mapping) -> dict:
    clean = {}
    for key, value in values.items():
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(value) and value > 0:
            clean[key] = value
    return clean


def normalize_weights(raw_weights: Mapping) -> dict:
    """Normalize a mapping of non-negative raw weights so the result sums to 1."""
    clean = _finite_positive(raw_weights)
    total = sum(clean.values())
    if total <= 0:
        return {}
    return {asset_id: weight / total for asset_id, weight in clean.items()}


def equal_weight(asset_ids: Sequence) -> dict:
    """Equal weights summing to 1.0 over the given assets."""
    assets = list(asset_ids)
    if not assets:
        return {}
    w = 1.0 / len(assets)
    return {asset_id: w for asset_id in assets}


def score_weight(
    ranked: pd.DataFrame,
    *,
    id_col: str = "asset_id",
    score_col: str = "composite_score",
) -> dict:
    """Weight selected assets in proportion to a positive signal score.

    If the score column is missing, non-finite, or non-positive for every name,
    the function falls back to equal weight. This keeps recommendation and
    backtest workflows robust when a strategy has sparse factor coverage.
    """
    if ranked.empty:
        return {}
    if score_col not in ranked.columns:
        return equal_weight(ranked[id_col].tolist())
    scores = ranked.set_index(id_col)[score_col].astype(float).clip(lower=0.0)
    weights = normalize_weights(scores.to_dict())
    return weights if weights else equal_weight(ranked[id_col].tolist())


def inverse_vol_weight(
    ranked: pd.DataFrame,
    *,
    id_col: str = "asset_id",
    vol_col: str = "volatility_252",
    vol_floor: float = 1e-8,
) -> dict:
    """Weight selected assets by inverse realized volatility.

    Lower-volatility names receive larger weights. Missing or non-positive
    volatility values are ignored. If every volatility value is unusable, the
    function falls back to equal weight.
    """
    if ranked.empty:
        return {}
    if vol_col not in ranked.columns:
        return equal_weight(ranked[id_col].tolist())

    raw = {}
    for asset_id, vol in ranked.set_index(id_col)[vol_col].items():
        try:
            vol = float(vol)
        except (TypeError, ValueError):
            continue
        if np.isfinite(vol) and vol > vol_floor:
            raw[asset_id] = 1.0 / vol
    weights = normalize_weights(raw)
    return weights if weights else equal_weight(ranked[id_col].tolist())


def target_weights(
    ranked: pd.DataFrame,
    top_n: int,
    weighting: str = "equal",
    id_col: str = "asset_id",
    score_col: str = "composite_score",
    vol_col: str = "volatility_252",
) -> dict:
    """Compute target portfolio weights from a ranked universe.

    Parameters
    ----------
    ranked:
        Universe ranked best-first.
    top_n:
        Number of names to hold.
    weighting:
        One of ``"equal"``, ``"score"``, or ``"inverse_vol"``.
    """
    if weighting not in SUPPORTED_WEIGHTINGS:
        raise NotImplementedError(
            f"weighting {weighting!r} not supported; choose one of {SUPPORTED_WEIGHTINGS}"
        )
    chosen = select_top_n(ranked, top_n)
    if weighting == "equal":
        return equal_weight(chosen[id_col].tolist())
    if weighting == "score":
        return score_weight(chosen, id_col=id_col, score_col=score_col)
    return inverse_vol_weight(chosen, id_col=id_col, vol_col=vol_col)
