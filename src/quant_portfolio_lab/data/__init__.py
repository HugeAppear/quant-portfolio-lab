"""Data layer: DuckDB schema, load/query helpers, and synthetic data."""

from .synthetic import make_synthetic_market

__all__ = [
    "SCHEMA_STATEMENTS",
    "get_connection",
    "init_schema",
    "make_synthetic_market",
]


def __getattr__(name: str):
    """Import DuckDB helpers lazily.

    This keeps synthetic-data workflows importable even in minimal environments
    where the optional runtime has not installed DuckDB yet. Calling one of the
    DuckDB helpers will still raise the normal ImportError if DuckDB is missing.
    """
    if name in {"SCHEMA_STATEMENTS", "get_connection", "init_schema"}:
        from .db import SCHEMA_STATEMENTS, get_connection, init_schema

        values = {
            "SCHEMA_STATEMENTS": SCHEMA_STATEMENTS,
            "get_connection": get_connection,
            "init_schema": init_schema,
        }
        return values[name]
    raise AttributeError(name)
