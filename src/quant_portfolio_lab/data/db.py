"""DuckDB connection management and schema definition.

The schema mirrors the entity model in the v0.1 spec:
``assets``, ``price_bars``, ``fundamental_snapshots``, ``factor_snapshots``,
``benchmark_prices``, ``backtest_runs``, ``backtest_positions``,
``backtest_trades``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path("data") / "quant_portfolio_lab.duckdb"

# Schema is intentionally declared as plain CREATE TABLE statements so it can be
# replayed against any DuckDB connection (file-backed or in-memory for tests).
SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS assets (
        asset_id      BIGINT PRIMARY KEY,
        symbol        VARCHAR NOT NULL,
        isin          VARCHAR,
        name          VARCHAR,
        asset_type    VARCHAR CHECK (asset_type IN ('EQUITY', 'ETF', 'INDEX')),
        country       VARCHAR,
        exchange      VARCHAR,
        currency      VARCHAR,
        market_segment VARCHAR,
        listing_date   DATE,
        delisting_date DATE,
        data_source    VARCHAR
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS price_bars (
        asset_id       BIGINT NOT NULL,
        date           DATE NOT NULL,
        open           DOUBLE,
        high           DOUBLE,
        low            DOUBLE,
        close          DOUBLE,
        adjusted_close DOUBLE,
        volume         DOUBLE,
        value_traded   DOUBLE,
        source         VARCHAR,
        PRIMARY KEY (asset_id, date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS fundamental_snapshots (
        asset_id           BIGINT NOT NULL,
        fiscal_period      VARCHAR NOT NULL,
        report_date        DATE NOT NULL,
        eps                DOUBLE,
        bps                DOUBLE,
        net_income         DOUBLE,
        total_equity       DOUBLE,
        shares_outstanding DOUBLE,
        source             VARCHAR,
        PRIMARY KEY (asset_id, fiscal_period)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS factor_snapshots (
        asset_id          BIGINT NOT NULL,
        as_of_date        DATE NOT NULL,
        price             DOUBLE,
        eps               DOUBLE,
        bps               DOUBLE,
        per               DOUBLE,
        pbr               DOUBLE,
        valid_for_backtest BOOLEAN,
        PRIMARY KEY (asset_id, as_of_date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS benchmark_prices (
        benchmark_id VARCHAR NOT NULL,
        date         DATE NOT NULL,
        close        DOUBLE,
        source       VARCHAR,
        PRIMARY KEY (benchmark_id, date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id              VARCHAR PRIMARY KEY,
        strategy_name       VARCHAR,
        universe            VARCHAR,
        rebalance_frequency VARCHAR,
        benchmark           VARCHAR,
        fee_rate            DOUBLE,
        tax_rate_policy     VARCHAR,
        slippage_policy     VARCHAR,
        delisting_policy    VARCHAR,
        created_at          TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_positions (
        run_id       VARCHAR NOT NULL,
        date         DATE NOT NULL,
        asset_id     BIGINT NOT NULL,
        weight       DOUBLE,
        quantity     DOUBLE,
        market_value DOUBLE,
        PRIMARY KEY (run_id, date, asset_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_trades (
        run_id          VARCHAR NOT NULL,
        date            DATE NOT NULL,
        asset_id        BIGINT NOT NULL,
        side            VARCHAR CHECK (side IN ('BUY', 'SELL')),
        quantity        DOUBLE,
        execution_price DOUBLE,
        gross_notional  DOUBLE,
        commission      DOUBLE,
        transaction_tax DOUBLE,
        slippage_cost   DOUBLE
    );
    """,
]


def get_connection(db_path: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection.

    Parameters
    ----------
    db_path:
        Path to the database file. Use ``":memory:"`` for a transient in-memory
        database (handy for tests). ``None`` uses :data:`DEFAULT_DB_PATH`.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create all v0.1 tables if they do not already exist."""
    for statement in SCHEMA_STATEMENTS:
        con.execute(statement)
