"""Thin launcher shim.

The real application lives in ``quant_portfolio_lab.api.main``; this module
keeps the historical ``uvicorn api.main:app`` entry point working.
"""

from quant_portfolio_lab.api.main import app

__all__ = ["app"]
