import { useState } from "react";
import type { CSSProperties } from "react";
import { api, useApi } from "../api/client";
import { num, pct, shortDate, theme } from "../theme";
import { ErrorState, Loading, PageHeader, Panel } from "../components/ui";
import {
  STRATEGIES,
  WEIGHTINGS,
  dataModeLabel,
  strategyLabel,
  type FactorSignal,
  type StrategyId,
  type WeightingId,
} from "../api/types";

const TOP_OPTIONS = [10, 20, 30, 50];

export default function ShortlistPage() {
  const [strategy, setStrategy] = useState<StrategyId>("value_momentum_quality");
  const [top, setTop] = useState(20);
  const [weighting, setWeighting] = useState<WeightingId>("equal");

  const { data, error, loading, refetch } = useApi(
    () => api.getShortlist({ strategy, top, weighting }),
    [strategy, top, weighting],
  );

  const isComposite = data?.items.some((i) => i.signals.length > 0) ?? false;

  return (
    <>
      <PageHeader
        title="Research shortlist"
        description="Current-date target portfolio for a strategy — the GUI twin of scripts/recommend.py. Research output only, not investment advice."
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value as StrategyId)} style={selectStyle}>
              {STRATEGIES.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
            <select value={weighting} onChange={(e) => setWeighting(e.target.value as WeightingId)} style={selectStyle}>
              {WEIGHTINGS.map((w) => (
                <option key={w.id} value={w.id}>{w.label}</option>
              ))}
            </select>
            <select value={top} onChange={(e) => setTop(Number(e.target.value))} style={selectStyle}>
              {TOP_OPTIONS.map((n) => (
                <option key={n} value={n}>Top {n}</option>
              ))}
            </select>
          </div>
        }
      />

      <Panel
        title={`${strategyLabel(strategy)} candidates`}
        subtitle={
          data
            ? `Generated ${shortDate(data.generatedAt)} · data as of ${shortDate(data.asOf)} · ${dataModeLabel(data.dataModeUsed)}`
            : undefined
        }
        padding={0}
      >
        {loading ? (
          <Loading label="Scoring candidates…" />
        ) : error ? (
          <ErrorState error={error} onRetry={refetch} />
        ) : !data || data.items.length === 0 ? (
          <div style={emptyStyle}>No candidates returned for these settings.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: "right", width: 44 }}>#</th>
                  <th style={{ ...thStyle, textAlign: "left" }}>Ticker</th>
                  <th style={{ ...thStyle, textAlign: "left" }}>Name</th>
                  <th style={{ ...thStyle, textAlign: "left" }}>Segment</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Weight</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Price</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>PER</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>PBR</th>
                  {isComposite && <th style={{ ...thStyle, textAlign: "right" }}>Score</th>}
                  {isComposite && (
                    <th style={{ ...thStyle, textAlign: "left", minWidth: 220 }}>Factor signals</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.ticker} className="qpl-row">
                    <td style={{ ...tdStyle, textAlign: "right", color: theme.color.faint, fontFamily: theme.font.mono }}>{item.rank}</td>
                    <td style={{ ...tdStyle, fontFamily: theme.font.mono, fontWeight: 600 }}>{item.ticker}</td>
                    <td style={tdStyle}>{item.name || "—"}</td>
                    <td style={{ ...tdStyle, color: theme.color.muted }}>{item.sector ?? "—"}</td>
                    <td style={{ ...numTd, fontWeight: 600 }}>{pct(item.targetWeight)}</td>
                    <td style={numTd}>{fmtPrice(item.price)}</td>
                    <td style={numTd}>{num(item.per, 1)}</td>
                    <td style={numTd}>{num(item.pbr, 2)}</td>
                    {isComposite && (
                      <td style={{ ...numTd, fontWeight: 600 }}>{num(item.score, 3)}</td>
                    )}
                    {isComposite && (
                      <td style={tdStyle}>
                        <SignalBars signals={item.signals} />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <p style={footnote}>
        The shortlist only appears in the CLI after a strategy passes backtest approval gates
        (scripts/recommend.py). Here it is always computed — validate a strategy on the Runs page
        before acting on anything.
      </p>
    </>
  );
}

function fmtPrice(v: number | null | undefined): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

/** Percentile scores in [0,1] rendered as compact labeled bars. */
function SignalBars({ signals }: { signals: FactorSignal[] }) {
  if (signals.length === 0) return <span style={{ color: theme.color.faint }}>—</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {signals.map((s) => (
        <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={signalLabelStyle}>{s.name}</span>
          <div style={signalTrackStyle}>
            <div
              style={{
                ...signalFillStyle,
                width: `${Math.max(0, Math.min(1, s.value)) * 100}%`,
                background: s.value >= 0.5 ? theme.color.positive : theme.color.warning,
              }}
            />
          </div>
          <span style={signalValueStyle}>{(s.value * 100).toFixed(0)}</span>
        </div>
      ))}
    </div>
  );
}

const selectStyle: CSSProperties = {
  appearance: "none",
  padding: "8px 11px",
  fontFamily: theme.font.sans,
  fontSize: 13,
  color: theme.color.ink,
  background: theme.color.surface,
  border: `1px solid ${theme.color.borderStrong}`,
  borderRadius: theme.radius.sm,
};
const tableStyle: CSSProperties = { width: "100%", borderCollapse: "collapse", fontFamily: theme.font.sans, fontSize: 13 };
const thStyle: CSSProperties = {
  padding: "9px 14px",
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: theme.color.faint,
  borderBottom: `1px solid ${theme.color.border}`,
  whiteSpace: "nowrap",
};
const tdStyle: CSSProperties = {
  padding: "10px 14px",
  borderBottom: `1px solid ${theme.color.grid}`,
  color: theme.color.ink,
  whiteSpace: "nowrap",
};
const numTd: CSSProperties = {
  ...tdStyle,
  textAlign: "right",
  fontFamily: theme.font.mono,
  fontVariantNumeric: "tabular-nums",
};
const signalLabelStyle: CSSProperties = {
  width: 68,
  flexShrink: 0,
  fontSize: 10.5,
  fontWeight: 600,
  letterSpacing: "0.03em",
  textTransform: "uppercase",
  color: theme.color.faint,
};
const signalTrackStyle: CSSProperties = {
  flex: 1,
  height: 5,
  minWidth: 70,
  background: theme.color.grid,
  borderRadius: 3,
  overflow: "hidden",
};
const signalFillStyle: CSSProperties = { height: "100%", borderRadius: 3 };
const signalValueStyle: CSSProperties = {
  width: 24,
  flexShrink: 0,
  textAlign: "right",
  fontFamily: theme.font.mono,
  fontSize: 10.5,
  color: theme.color.muted,
  fontVariantNumeric: "tabular-nums",
};
const emptyStyle: CSSProperties = { padding: 24, textAlign: "center", color: theme.color.muted, fontSize: 14 };
const footnote: CSSProperties = {
  marginTop: 14,
  fontSize: 12,
  color: theme.color.faint,
  lineHeight: 1.5,
};
