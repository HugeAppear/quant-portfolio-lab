import { useState } from "react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { theme } from "../theme";
import { Button } from "./ui";
import {
  REBALANCE_FREQUENCIES,
  STRATEGIES,
  UNIVERSES,
  type RebalanceFrequency,
  type RunConfig,
  type StrategyId,
  type UniverseId,
} from "../api/types";

interface RunControlsProps {
  onSubmit: (config: RunConfig) => void;
  submitting?: boolean;
}

const TODAY = new Date().toISOString().slice(0, 10);
const DEFAULT_START = "2015-01-01";

// Strategy-specific numeric parameters surfaced as extra fields.
const STRATEGY_PARAMS: Record<StrategyId, { key: string; label: string; default: number; step?: number }[]> = {
  momentum: [
    { key: "lookback", label: "Lookback (days)", default: 126 },
    { key: "holding", label: "Holding (days)", default: 21 },
    { key: "topN", label: "Top N names", default: 30 },
  ],
  mean_reversion: [
    { key: "lookback", label: "Lookback (days)", default: 5 },
    { key: "zEntry", label: "Z entry", default: 1.5, step: 0.1 },
  ],
  stat_arb: [
    { key: "lookback", label: "Lookback (days)", default: 60 },
    { key: "zEntry", label: "Z entry", default: 2, step: 0.1 },
    { key: "zExit", label: "Z exit", default: 0.5, step: 0.1 },
  ],
  value: [{ key: "topN", label: "Top N names", default: 50 }],
  low_vol: [{ key: "topN", label: "Top N names", default: 50 }],
  ml: [
    { key: "trainWindow", label: "Train window (days)", default: 504 },
    { key: "topN", label: "Top N names", default: 30 },
  ],
  equal_weight: [],
};

function defaultsFor(strategy: StrategyId): Record<string, number> {
  return Object.fromEntries(STRATEGY_PARAMS[strategy].map((p) => [p.key, p.default]));
}

export default function RunControls({ onSubmit, submitting }: RunControlsProps) {
  const [strategy, setStrategy] = useState<StrategyId>("momentum");
  const [universe, setUniverse] = useState<UniverseId>(UNIVERSES[0].id);
  const [startDate, setStartDate] = useState(DEFAULT_START);
  const [endDate, setEndDate] = useState(TODAY);
  const [rebalance, setRebalance] = useState<RebalanceFrequency>("monthly");
  const [initialCapital, setInitialCapital] = useState(1_000_000);
  const [costBps, setCostBps] = useState(5);
  const [slippageBps, setSlippageBps] = useState(2);
  const [params, setParams] = useState<Record<string, number>>(defaultsFor("momentum"));

  const onStrategyChange = (id: StrategyId) => {
    setStrategy(id);
    setParams(defaultsFor(id));
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      strategy,
      universe,
      startDate,
      endDate,
      rebalance,
      initialCapital,
      transactionCostBps: costBps,
      slippageBps,
      params,
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div style={gridStyle}>
        <Field label="Strategy">
          <select value={strategy} onChange={(e) => onStrategyChange(e.target.value as StrategyId)} style={inputStyle}>
            {STRATEGIES.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Universe">
          <select value={universe} onChange={(e) => setUniverse(e.target.value as UniverseId)} style={inputStyle}>
            {UNIVERSES.map((u) => (
              <option key={u.id} value={u.id}>{u.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Rebalance">
          <select value={rebalance} onChange={(e) => setRebalance(e.target.value as RebalanceFrequency)} style={inputStyle}>
            {REBALANCE_FREQUENCIES.map((r) => (
              <option key={r.id} value={r.id}>{r.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Start date">
          <input type="date" value={startDate} max={endDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
        </Field>

        <Field label="End date">
          <input type="date" value={endDate} min={startDate} max={TODAY} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
        </Field>

        <Field label="Initial capital ($)">
          <input type="number" min={1000} step={1000} value={initialCapital} onChange={(e) => setInitialCapital(Number(e.target.value))} style={numInputStyle} />
        </Field>

        <Field label="Cost (bps)">
          <input type="number" min={0} step={0.5} value={costBps} onChange={(e) => setCostBps(Number(e.target.value))} style={numInputStyle} />
        </Field>

        <Field label="Slippage (bps)">
          <input type="number" min={0} step={0.5} value={slippageBps} onChange={(e) => setSlippageBps(Number(e.target.value))} style={numInputStyle} />
        </Field>

        {STRATEGY_PARAMS[strategy].map((p) => (
          <Field key={p.key} label={p.label}>
            <input
              type="number"
              step={p.step ?? 1}
              value={params[p.key] ?? p.default}
              onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: Number(e.target.value) }))}
              style={numInputStyle}
            />
          </Field>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Running…" : "Run backtest"}
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label style={fieldStyle}>
      <span style={fieldLabelStyle}>{label}</span>
      {children}
    </label>
  );
}

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
  gap: 14,
};
const fieldStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 6, minWidth: 0 };
const fieldLabelStyle: CSSProperties = {
  fontFamily: theme.font.sans,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: theme.color.faint,
};
const inputStyle: CSSProperties = {
  appearance: "none",
  width: "100%",
  boxSizing: "border-box",
  padding: "9px 11px",
  fontFamily: theme.font.sans,
  fontSize: 13.5,
  color: theme.color.ink,
  background: theme.color.surface,
  border: `1px solid ${theme.color.borderStrong}`,
  borderRadius: theme.radius.sm,
};
const numInputStyle: CSSProperties = {
  ...inputStyle,
  fontFamily: theme.font.mono,
  fontVariantNumeric: "tabular-nums",
};
