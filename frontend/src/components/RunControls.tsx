import { useState } from "react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { theme } from "../theme";
import { Button } from "./ui";
import {
  DATA_MODES,
  REBALANCE_FREQUENCIES,
  STRATEGIES,
  WEIGHTINGS,
  type DataMode,
  type RebalanceFrequency,
  type RunConfig,
  type StrategyId,
  type WeightingId,
} from "../api/types";

interface RunControlsProps {
  onSubmit: (config: RunConfig) => void;
  submitting?: boolean;
}

const TODAY = new Date().toISOString().slice(0, 10);

export default function RunControls({ onSubmit, submitting }: RunControlsProps) {
  const [strategy, setStrategy] = useState<StrategyId>("low_pbr");
  const [rebalance, setRebalance] = useState<RebalanceFrequency>("1Y");
  const [topN, setTopN] = useState(20);
  const [weighting, setWeighting] = useState<WeightingId>("equal");
  const [benchmark, setBenchmark] = useState("KOSPI");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialCapital, setInitialCapital] = useState(10_000_000);
  const [feeBps, setFeeBps] = useState(10);
  const [taxBps, setTaxBps] = useState(20);
  const [slippageBps, setSlippageBps] = useState(20);
  const [dataMode, setDataMode] = useState<DataMode>("auto");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      strategy,
      rebalance,
      topN,
      weighting,
      benchmark: benchmark.trim() || "KOSPI",
      startDate: startDate || null,
      endDate: endDate || null,
      initialCapital,
      feeBps,
      taxBps,
      slippageBps,
      dataMode,
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div style={gridStyle}>
        <Field label="Strategy">
          <select value={strategy} onChange={(e) => setStrategy(e.target.value as StrategyId)} style={inputStyle}>
            {STRATEGIES.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
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

        <Field label="Top N names">
          <input type="number" min={2} max={50} step={1} value={topN} onChange={(e) => setTopN(Number(e.target.value))} style={numInputStyle} />
        </Field>

        <Field label="Weighting">
          <select value={weighting} onChange={(e) => setWeighting(e.target.value as WeightingId)} style={inputStyle}>
            {WEIGHTINGS.map((w) => (
              <option key={w.id} value={w.id}>{w.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Benchmark">
          <input type="text" value={benchmark} onChange={(e) => setBenchmark(e.target.value)} style={inputStyle} placeholder="KOSPI" />
        </Field>

        <Field label="Data">
          <select value={dataMode} onChange={(e) => setDataMode(e.target.value as DataMode)} style={inputStyle}>
            {DATA_MODES.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Start date (optional)">
          <input type="date" value={startDate} max={endDate || TODAY} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
        </Field>

        <Field label="End date (optional)">
          <input type="date" value={endDate} min={startDate || undefined} max={TODAY} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
        </Field>

        <Field label="Initial capital (₩)">
          <input type="number" min={100_000} step={100_000} value={initialCapital} onChange={(e) => setInitialCapital(Number(e.target.value))} style={numInputStyle} />
        </Field>

        <Field label="Fee (bps)">
          <input type="number" min={0} step={0.5} value={feeBps} onChange={(e) => setFeeBps(Number(e.target.value))} style={numInputStyle} />
        </Field>

        <Field label="Sell tax (bps)">
          <input type="number" min={0} step={0.5} value={taxBps} onChange={(e) => setTaxBps(Number(e.target.value))} style={numInputStyle} />
        </Field>

        <Field label="Slippage (bps)">
          <input type="number" min={0} step={0.5} value={slippageBps} onChange={(e) => setSlippageBps(Number(e.target.value))} style={numInputStyle} />
        </Field>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16, gap: 12 }}>
        <span style={hintStyle}>
          Leave dates empty to use the full available history. Costs are in basis points (10 bps = 0.10%).
        </span>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Starting…" : "Run backtest"}
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
const hintStyle: CSSProperties = {
  fontSize: 12,
  color: theme.color.faint,
  lineHeight: 1.4,
};
