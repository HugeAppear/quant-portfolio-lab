from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quant_portfolio_lab.api.schemas import BacktestRequest
from quant_portfolio_lab.api.services import run_backtest_service

app = FastAPI(
    title="Quant Portfolio Lab API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/backtests")
def run_backtest(request: BacktestRequest):
    return run_backtest_service(request)