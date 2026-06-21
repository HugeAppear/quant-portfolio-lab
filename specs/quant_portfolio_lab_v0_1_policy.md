# Quant Portfolio Lab v0.1 Policy

## 1. Project Purpose

Quant Portfolio Lab is a personal analytics and research platform.

It organizes, processes, backtests, and visualizes financial data to help evaluate market trends, portfolio performance, and potential risks.

The platform does **not** provide personalized investment recommendations, does **not** act as a fiduciary, and does **not** execute trades.

All final investment decisions remain entirely with the user.

---

## 2. Supported Assets

The platform supports the following asset types:

- Equities
- ETFs
- Market indices used as benchmarks

---

## 3. Supported Data

The platform uses historical time-series data for:

- Equities
- ETFs
- Key global indices

Initial benchmark indices:

- S&P 500
- Dow Jones Industrial Average
- KOSPI

---

## 4. Valuation Factors

PER is defined as:

```text
PER = Stock Price / Earnings Per Share
```

PBR is defined as:

```text
PBR = Stock Price / Book Value Per Share
```

PER and PBR strategies are mainly applied to individual equities.

ETFs may be used for portfolio visualization, allocation analysis, and benchmark comparison.

---

## 5. Rebalancing Policy

The platform supports two rebalancing strategies:

- 6-month rebalancing
- 1-year rebalancing

If a scheduled rebalance date is not a trading day, the next available trading day is used.

---

## 6. Benchmark Policy

Supported benchmarks:

- S&P 500
- Dow Jones Industrial Average
- KOSPI

Benchmarks are used for performance comparison.

They are not treated as directly tradable assets unless mapped to ETF proxies.

---

## 7. Cost Policy

### Brokerage Fee

```text
0.1% per side
```

The brokerage fee applies to both buy and sell trades.

### Securities Transaction Tax

```text
0.20% on sell trades
```

The tax rate should be configurable because tax rules may change over time.

---

## 8. Slippage Policy

Default slippage assumptions:

| Asset Type | Slippage Assumption |
|---|---:|
| High-liquidity assets | 0.1% to 0.3% |
| Illiquid or micro-cap assets | 0.5% to 1.0% |

Buy execution price:

```text
Buy Execution Price = Close Price * (1 + Slippage Rate)
```

Sell execution price:

```text
Sell Execution Price = Close Price * (1 - Slippage Rate)
```

---

## 9. Delisting Policy

If a delisting event is detected, the default conservative assumption is:

```text
100% loss
```

This is a backtest scenario assumption, not a universal real-world rule.

---

## 10. First MVP Strategy

The first MVP strategy is defined as follows:

| Category | Rule |
|---|---|
| Universe | Korean common equities |
| Factor | Lowest PBR |
| Portfolio Size | Top 20 or Top 30 stocks |
| Weighting | Equal weight |
| Rebalancing | 1-year first, then 6-month |
| Benchmark | KOSPI |

Cost assumptions:

| Cost Type | Assumption |
|---|---:|
| Brokerage fee | 0.1% per side |
| Securities transaction tax | 0.20% on sell trades |
| Slippage | 0.1% to 0.3% for liquid stocks |

---

## 11. Non-Goals for v0.1

The first version will not include:

- Real-time trading
- Trade execution
- Personalized investment recommendations
- Commercial data redistribution
- Crypto backtesting
- Advanced portfolio optimization