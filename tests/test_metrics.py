import pandas as pd
import pytest

from quant_portfolio_lab.backtest.metrics import cagr, excess_cagr, performance_summary

def test_excess_cagr_positive_when_strategy_compounds_faster():
    dates = pd.bdate_range("2020-01-01", periods=253)
    
    strategy = pd.Series(
        [100.0 + i * (20.0 / 252) for i in range(253)],
        index=dates,
    )
    benchmark = pd.Series(
        [100.0 + i * (10.0 / 252) for i in range(253)],
        index=dates,
    )
    
    got = excess_cagr(strategy, benchmark)
    
    assert got == pytest.approx(cagr(strategy) - cagr(benchmark))
    assert got > 0
    

def test_performance_summary_includes_excess_cagr_when_benchmark_is_present():
    dates = pd.bdate_range("2020-01-01", periods=253)
    strategy = pd.Series(100.0, index=dates)
    benchmark = pd.Series(100.0, index=dates)
    
    summary = performance_summary(strategy, benchmark=benchmark)
    
    assert "benchmark_cagr" in summary
    assert "excess_cagr" in summary
    assert summary["excess_cagr"] == pytest.approx(0.0)