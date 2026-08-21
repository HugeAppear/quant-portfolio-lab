"""FastAPI application for the quant-portfolio-lab web GUI.

Run in development (frontend served separately by Vite on :5173):

    uvicorn quant_portfolio_lab.api.main:app --reload --port 8000

Production-style single process (after ``npm run build`` in ``frontend/``):

    uvicorn quant_portfolio_lab.api.main:app --port 8000
    # -> http://localhost:8000 serves the built GUI and the API together.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .jobs import DataJobManager
from .schemas import (
    DashboardData,
    DataHealth,
    DataJob,
    DataLoadRequest,
    Run,
    RunConfig,
    RunSummary,
    Shortlist,
)
from .services import RunManager, _now_iso, build_data_health, build_shortlist
from .store import RunStore

DB_PATH = os.environ.get("QPL_DB_PATH")  # None -> data/quant_portfolio_lab.duckdb

app = FastAPI(title="Quant Portfolio Lab API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = RunStore(DB_PATH)
runs = RunManager(store)
data_jobs = DataJobManager(DB_PATH)


# ---------------------------------------------------------------------------
# Health / dashboard
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard", response_model=DashboardData)
def dashboard() -> DashboardData:
    return DashboardData(
        asOf=_now_iso(),
        runCount=store.count(),
        latestRun=store.latest_completed(),
    )


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

@app.get("/api/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    return store.list_summaries()


@app.post("/api/runs", response_model=Run)
def create_run(config: RunConfig) -> Run:
    return runs.submit(config)


@app.get("/api/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return run


@app.post("/api/runs/{run_id}/cancel", response_model=Run)
def cancel_run(run_id: str) -> Run:
    run = runs.cancel(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return run


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, bool]:
    if not store.delete(run_id):
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------

@app.get("/api/shortlist", response_model=Shortlist)
def shortlist(
    strategy: str = "low_pbr",
    top: int = 20,
    weighting: str = "equal",
    asOfDate: str | None = None,
    dataMode: str = "auto",
) -> Shortlist:
    try:
        return build_shortlist(
            strategy,
            top_n=max(1, min(top, 50)),
            weighting=weighting,
            as_of_date=asOfDate,
            data_mode=dataMode,
            db_path=DB_PATH,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Data health / data jobs
# ---------------------------------------------------------------------------

@app.get("/api/data-health", response_model=DataHealth)
def data_health() -> DataHealth:
    return build_data_health(DB_PATH)


@app.get("/api/data/jobs", response_model=list[DataJob])
def list_data_jobs() -> list[DataJob]:
    return data_jobs.list()


@app.post("/api/data/load", response_model=DataJob)
def load_data(request: DataLoadRequest) -> DataJob:
    if data_jobs.has_active():
        raise HTTPException(
            status_code=409, detail="A data load is already in progress."
        )
    return data_jobs.submit(request)


@app.get("/api/data/jobs/{job_id}", response_model=DataJob)
def get_data_job(job_id: str) -> DataJob:
    job = data_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return job


# ---------------------------------------------------------------------------
# Static frontend (optional): serve frontend/dist when it exists.
# ---------------------------------------------------------------------------

class _SPAStaticFiles(StaticFiles):
    """Serve the built SPA; unknown paths fall back to index.html so
    client-side routes like /runs survive a page refresh."""

    async def get_response(self, path: str, scope):
        from starlette.exceptions import HTTPException as StarletteHTTPException

        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response


_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", _SPAStaticFiles(directory=str(_DIST), html=True), name="frontend")
