"""Data layer: DuckDB schema, load/query helpers, and synthetic data."""

from .db import SCHEMA_STATEMENTS, get_connection, init_schema
from .synthetic import make_synthetic_market

__all__ = [
    "SCHEMA_STATEMENTS",
    "get_connection",
    "init_schema",
    "make_synthetic_market",
]
