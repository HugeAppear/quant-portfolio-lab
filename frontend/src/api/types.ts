// Shared domain types for the quant-portfolio-lab frontend.
// These mirror the pydantic models in src/quant_portfolio_lab/api/schemas.py
// one-to-one (same camelCase field names) — change them together.

// ---------------------------------------------------------------------------
// Option lists (drive the run-config form; must match the Python engine)
// ---------------------------------------------------------------------------

export const STRATEGIES = [
  { id: "low_pbr", label: "Low PBR (value)" },
  { id: "low_per", label: "Low PER (value)" },
  { id: "value_momentum_quality", label: "Value + Momentum + Quality" },
  { id: "defensive_value", label: "Defensive value (low vol tilt)" },
  { id: "momentum_lowvol", label: "Momentum + Low volatility" },
] as const;
export type StrategyId = (typeof STRATEGIES)[number]["id"];

export const REBALANCE_FREQUENCIES = [
  { id: "6M", label: "Every 6 months" },
  { id: "1Y", label: "Yearly" },
] as const;
export type RebalanceFrequency = (typeof REBALANCE_FREQUENCIES)[number]["id"];

export const WEIGHTINGS = [
  { id: "equal", label: "Equal weight" },
  { id: "score", label: "Score weighted" },
  { id: "inverse_vol", label: "Inverse volatility" },
] as const;
export type WeightingId = (typeof WEIGHTINGS)[number]["id"];

export const DATA_MODES = [
  { id: "auto", label: "Auto (DuckDB → synthetic)" },
  { id: "synthetic", label: "Synthetic (offline demo)" },
] as const;
export type DataMode = (typeof DATA_MODES)[number]["id"];

export function strategyLabel(id: StrategyId): string {
  return STRATEGIES.find((s) => s.id === id)?.label ?? id;
}
export function weightingLabel(id: WeightingId): string {
  return WEIGHTINGS.find((w) => w.id === id)?.label ?? id;
}
export function dataModeLabel(mode: string | null | undefined): string {
  if (mode === "duckdb") return "DuckDB (real data)";
  if (mode === "synthetic") return "Synthetic data";
  return mode ?? "—";
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export const ACTIVE_RUN_STATUSES: RunStatus[] = ["queued", "running"];

export interface RunConfig {
  strategy: StrategyId;
  rebalance: RebalanceFrequency;
  topN: number;
  weighting: WeightingId;
  benchmark: string;             // e.g. "KOSPI"
  startDate?: string | null;     // ISO yyyy-mm-dd; null = full history
  endDate?: string | null;
  initialCapital: number;        // KRW
  feeBps: number;                // brokerage fee, basis points
  taxBps: number;                // sell-side transaction tax, basis points
  slippageBps: number;
  dataMode: DataMode;
}

export interface Metrics {
  totalReturn?: number | null;   // fraction, e.g. 0.84 == +84%
  cagr?: number | null;
  volatility?: number | null;    // annualized fraction
  sharpe?: number | null;
  sortino?: number | null;
  maxDrawdown?: number | null;   // negative fraction
  calmar?: number | null;
  winRate?: number | null;       // fraction of up days
  turnover?: number | null;      // average per-rebalance turnover
  finalValue?: number | null;    // KRW
  benchmarkTotalReturn?: number | null;
  benchmarkCagr?: number | null;
  excessCagr?: number | null;
  benchmarkMaxDrawdown?: number | null;
}

export interface EquityPoint {
  date: string;                  // ISO date
  equity: number;                // portfolio value (KRW)
  benchmark?: number | null;     // benchmark rebased to the same start capital
  drawdown?: number | null;      // negative fraction
}

export interface Holding {
  ticker: string;
  name?: string | null;
  sector?: string | null;        // market segment (KOSPI / KOSDAQ)
  weight: number;
  shares?: number | null;
  value?: number | null;         // KRW
}

export interface AllocationPoint {
  date: string;
  weights: Record<string, number>; // ticker -> weight fraction
}

export interface RunSummary {
  id: string;
  createdAt: string;             // ISO timestamp
  status: RunStatus;
  strategy: StrategyId;
  rebalance: RebalanceFrequency;
  topN: number;
  weighting: WeightingId;
  dataModeUsed?: string | null;  // "duckdb" | "synthetic"
  metrics?: Metrics | null;
}

export interface Run extends RunSummary {
  config: RunConfig;
  equityCurve?: EquityPoint[] | null;
  holdings?: Holding[] | null;
  allocation?: AllocationPoint[] | null;
  error?: string | null;
}

export interface DashboardData {
  asOf: string;
  runCount: number;
  latestRun?: Run | null;
}

// ---------------------------------------------------------------------------
// Research shortlist (recommendation module)
// ---------------------------------------------------------------------------

export interface FactorSignal {
  name: string;                  // "value" | "momentum" | "low vol" | "quality"
  value: number;                 // percentile score in [0, 1]
}

export interface ShortlistItem {
  rank: number;
  ticker: string;
  name: string;
  sector?: string | null;
  score?: number | null;
  targetWeight?: number | null;
  price?: number | null;
  per?: number | null;
  pbr?: number | null;
  signals: FactorSignal[];
}

export interface Shortlist {
  generatedAt: string;
  asOf: string;
  strategy: StrategyId;
  weighting: WeightingId;
  dataModeUsed: string;
  items: ShortlistItem[];
}

// ---------------------------------------------------------------------------
// Data health / data jobs
// ---------------------------------------------------------------------------

export type HealthStatus = "ok" | "warning" | "error";

export interface DataHealthCheck {
  source: string;
  status: HealthStatus;
  lastUpdated?: string | null;
  rows?: number | null;
  symbols?: number | null;
  staleDays?: number | null;
  message?: string | null;
}

export interface DataHealth {
  checkedAt: string;
  dbPath: string;
  checks: DataHealthCheck[];
}

export interface DataLoadRequest {
  kind: "prices" | "fundamentals" | "all";
  start: string;
  end?: string | null;
  universeSize: number;
  synthetic: boolean;
}

export interface DataJob {
  id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed";
  createdAt: string;
  finishedAt?: string | null;
  logTail: string[];
  error?: string | null;
}
