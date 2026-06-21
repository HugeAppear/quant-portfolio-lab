"""Portfolio construction: top-N selection and weighting.

v0.1 supports a single weighting scheme -- equal weight over the top-N ranked
names (spec section 10). Kept separate from the engine so alternative weightings
can be added later without touching the backtest loop.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def select_top_n(ranked: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return the top ``n`` rows of a frame already ranked best-first."""
    if n <= 0:
        raise ValueError("n must be positive")
    return ranked.head(n).copy()


def equal_weight(asset_ids: Sequence) -> dict:
    """Equal weights summing to 1.0 over the given assets."""
    assets = list(asset_ids)
    if not assets:
        return {}
    w = 1.0 / len(assets)
    return {asset_id: w for asset_id in assets}


def target_weights(
    ranked: pd.DataFrame,
    top_n: int,
    weighting: str = "equal",
    id_col: str = "asset_id",
) -> dict:
    """Compute target portfolio weights from a ranked universe.

    Parameters
    ----------
    ranked:
        Universe ranked best-first (e.g. lowest PBR first).
    top_n:
        Number of names to hold.
    weighting:
        Only ``"equal"`` is supported in v0.1.
    """
    if weighting != "equal":
        raise NotImplementedError(f"weighting {weighting!r} not supported in v0.1")
    chosen = select_top_n(ranked, top_n)
    return equal_weight(chosen[id_col].tolist())
