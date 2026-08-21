"""Run-history persistence for the web GUI.

App runs live in an ``app_runs`` table inside the same DuckDB file as the
market data, so history survives restarts with zero extra setup. Result series
(equity curve, holdings, allocation) are stored as JSON documents — they are
read back only to render a run, never queried relationally.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..data.db import get_connection, init_schema
from .inputs import DB_LOCK, resolve_db_path
from .schemas import (
    AllocationPoint,
    EquityPoint,
    Holding,
    Metrics,
    Run,
    RunConfig,
    RunSummary,
)

APP_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_runs (
    run_id        VARCHAR PRIMARY KEY,
    created_at    VARCHAR,
    status        VARCHAR,
    strategy      VARCHAR,
    rebalance     VARCHAR,
    top_n         INTEGER,
    weighting     VARCHAR,
    data_mode_used VARCHAR,
    config_json   VARCHAR,
    metrics_json  VARCHAR,
    equity_json   VARCHAR,
    holdings_json VARCHAR,
    allocation_json VARCHAR,
    error         VARCHAR
);
"""


class RunStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_db_path(db_path)

    def _connect(self):
        con = get_connection(self.db_path)
        init_schema(con)
        con.execute(APP_RUNS_SCHEMA)
        return con

    # ------------------------------------------------------------------ write
    def create(self, run: Run) -> None:
        with DB_LOCK:
            con = self._connect()
            try:
                con.execute(
                    "INSERT OR REPLACE INTO app_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    self._row(run),
                )
            finally:
                con.close()

    def update(self, run: Run) -> None:
        self.create(run)

    def _row(self, run: Run) -> list:
        return [
            run.id,
            run.createdAt,
            run.status,
            run.strategy,
            run.rebalance,
            run.topN,
            run.weighting,
            run.dataModeUsed,
            run.config.model_dump_json(),
            run.metrics.model_dump_json() if run.metrics else None,
            json.dumps([p.model_dump() for p in run.equityCurve]) if run.equityCurve else None,
            json.dumps([h.model_dump() for h in run.holdings]) if run.holdings else None,
            json.dumps([a.model_dump() for a in run.allocation]) if run.allocation else None,
            run.error,
        ]

    # ------------------------------------------------------------------- read
    def list_summaries(self, limit: int = 200) -> list[RunSummary]:
        with DB_LOCK:
            con = self._connect()
            try:
                rows = con.execute(
                    """
                    SELECT run_id, created_at, status, strategy, rebalance, top_n,
                           weighting, data_mode_used, metrics_json
                    FROM app_runs ORDER BY created_at DESC LIMIT ?
                    """,
                    [limit],
                ).fetchall()
            finally:
                con.close()
        out = []
        for r in rows:
            out.append(
                RunSummary(
                    id=r[0], createdAt=r[1], status=r[2], strategy=r[3],
                    rebalance=r[4], topN=r[5], weighting=r[6], dataModeUsed=r[7],
                    metrics=Metrics(**json.loads(r[8])) if r[8] else None,
                )
            )
        return out

    def get(self, run_id: str) -> Run | None:
        with DB_LOCK:
            con = self._connect()
            try:
                row = con.execute(
                    "SELECT * FROM app_runs WHERE run_id = ?", [run_id]
                ).fetchone()
            finally:
                con.close()
        if row is None:
            return None
        (rid, created, status, strategy, rebalance, top_n, weighting, mode,
         config_json, metrics_json, equity_json, holdings_json, alloc_json, error) = row
        return Run(
            id=rid, createdAt=created, status=status, strategy=strategy,
            rebalance=rebalance, topN=top_n, weighting=weighting, dataModeUsed=mode,
            config=RunConfig(**json.loads(config_json)),
            metrics=Metrics(**json.loads(metrics_json)) if metrics_json else None,
            equityCurve=[EquityPoint(**p) for p in json.loads(equity_json)] if equity_json else None,
            holdings=[Holding(**h) for h in json.loads(holdings_json)] if holdings_json else None,
            allocation=[AllocationPoint(**a) for a in json.loads(alloc_json)] if alloc_json else None,
            error=error,
        )

    def latest_completed(self) -> Run | None:
        with DB_LOCK:
            con = self._connect()
            try:
                row = con.execute(
                    """
                    SELECT run_id FROM app_runs WHERE status = 'completed'
                    ORDER BY created_at DESC LIMIT 1
                    """
                ).fetchone()
            finally:
                con.close()
        return self.get(row[0]) if row else None

    def count(self) -> int:
        with DB_LOCK:
            con = self._connect()
            try:
                return int(con.execute("SELECT COUNT(*) FROM app_runs").fetchone()[0])
            finally:
                con.close()

    def delete(self, run_id: str) -> bool:
        with DB_LOCK:
            con = self._connect()
            try:
                existed = con.execute(
                    "SELECT 1 FROM app_runs WHERE run_id = ?", [run_id]
                ).fetchone() is not None
                con.execute("DELETE FROM app_runs WHERE run_id = ?", [run_id])
            finally:
                con.close()
        return existed
