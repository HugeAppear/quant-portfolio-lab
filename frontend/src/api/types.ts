// Shared domain types for the quant-portfolio-lab frontend.
// These mirror the JSON the backend is expected to return. Adjust field names
// here if your API uses different ones — the rest of the app keys off this file.

// ---------------------------------------------------------------------------
// Option lists (also drive the run-config form)
// ---------------------------------------------------------------------------

export const STRATEGIES = [
  { id: "momentum", label: "Cross-sectional momentum" },
  { id: "mean_reversion", label: "Short-term mean reversion" },
  { id: "stat_arb", label: "Statistical arbitrage (pairs)" },
  { id: "value", label: "Value factor" },
  { id: "low_vol", label: "Low volatility" },
  { id: "ml", label: "ML ensemble" },
  { id: "equal_weight", label: "Equal weight (benchmark)" },
] as const;
export type StrategyId = (typeof STRATEGIES)[number]["id"];

export const REBALANCE_FREQUENCIES = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "quarterly", label: "Quarterly" },
] as const;
export type RebalanceFrequency = (typeof REBALANCE_FREQUENCIES)[number]["id"];

export const UNIVERSES = [
  { id: "sp500", label: "S&P 500" },
  { id: "nasdaq100", label: "Nasdaq 100" },
  { id: "russell1000", label: "Russell 1000" },
  { id: "custom", label: "Custom watchlist" },
] as const;
export type UniverseId = (typeof UNIVERSES)[number]["id"];

export function strategyLabel(id: StrategyId): string {
  return STRATEGIES.find((s) => s.id === id)?.label ?? id;
}
export function universeLabel(id: UniverseId): string {
  return UNIVERSES.find((u) => u.id === id)?.label ?? id;
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface RunConfig {
  strategy: StrategyId;
  universe: UniverseId;
  startDate: string; // ISO yyyy-mm-dd
  endDate: string; // ISO yyyy-mm-dd
  rebalance: RebalanceFrequency;
  initialCapital: number;
  transactionCostBps: number;
  slippageBps: number;
  params: Record<string, number | string | boolean>;
}

export interface Metrics {
  totalReturn: number; // fraction, e.g. 1.84 == +184%
  cagr: number; // fraction
  volatility: number; // annualized fraction
  sharpe: number;
  sortino: number;
  maxDrawdown: number; // negative fraction, e.g. -0.32
  calmar: number;
  winRate: number; // fraction
  turnover: number; // annualized fraction
}

export interface EquityPoint {
  date: string; // ISO date
  equity: number; // portfolio value
  benchmark?: number; // benchmark value on the same base
  drawdown?: number; // negative fraction
}

export interface Holding {
  ticker: string;
  name?: string;
  sector?: string;
  weight: number; // fraction of portfolio
  shares?: number;
  value?: number;
}

export interface AllocationPoint {
  date: string; // ISO date
  weights: Record<string, number>; // ticker -> weight fraction
}

export interface RunSummary {
  id: string;
  createdAt: string; // ISO timestamp
  status: RunStatus;
  strategy: StrategyId;
  universe: UniverseId;
  metrics?: Partial<Metrics>; // light metrics for the list view
}

export interface Run extends RunSummary {
  config: RunConfig;
  metrics?: Metrics;
  equityCurve?: EquityPoint[];
  holdings?: Holding[];
  allocation?: AllocationPoint[];
  error?: string;
}

export interface DashboardData {
  asOf: string; // ISO timestamp
  runCount: number;
  latestRun?: Run;
}

// ---------------------------------------------------------------------------
// Research shortlist (scripts/recommend.py)
// ---------------------------------------------------------------------------

export interface FactorSignal {
  name: string; // e.g. "momentum", "value", "quality"
  value: number; // normalized score, typically a z-score in roughly [-3, 3]
}

export interface ShortlistItem {
  rank: number;
  ticker: string;
  name: string;
  sector?: string;
  score: number; // composite score
  signals: FactorSignal[];
  rationale?: string;
}

export interface Shortlist {
  generatedAt: string; // ISO timestamp
  asOf: string; // data as-of date
  universe: UniverseId;
  items: ShortlistItem[];
}

// ---------------------------------------------------------------------------
// Data health
// ---------------------------------------------------------------------------

export type HealthStatus = "ok" | "warning" | "error";

export interface DataHealthCheck {
  source: string; // e.g. "prices: equities"
  status: HealthStatus;
  lastUpdated?: string; // ISO date
  rows?: number;
  symbols?: number;
  missingSessions?: number;
  staleDays?: number;
  message?: string;
}

export interface DataHealth {
  checkedAt: string; // ISO timestamp
  checks: DataHealthCheck[];
}
