import { useState } from "react";
import type { CSSProperties } from "react";
import { api, useApi } from "../api/client";
import { num, shortDate } from "../theme";
import { theme } from "../theme";
import { ErrorState, Loading, PageHeader, Panel } from "../components/ui";
import { UNIVERSES, universeLabel, type FactorSignal, type UniverseId } from "../api/types";

const TOP_OPTIONS = [10, 25, 50];

export default function ShortlistPage() {
  const [universe, setUniverse] = useState<UniverseId>(UNIVERSES[0].id);
  const [top, setTop] = useState(25);

  const { data, error, loading, refetch } = useApi(
    () => api.getShortlist({ universe, top }),
    [universe, top],
  );

  return (
    <>
      <PageHeader
        title="Research shortlist"
        description="Ranked candidates from scripts/recommend.py, scored across factor signals."
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <select value={universe} onChange={(e) => setUniverse(e.target.value as UniverseId)} style={selectStyle}>
              {UNIVERSES.map((u) => (
                <option key={u.id} value={u.id}>{u.label}</option>
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
        title={`${universeLabel(universe)} candidates`}
        subtitle={data ? `Generated ${shortDate(data.generatedAt)} · data as of ${shortDate(data.asOf)}` : undefined}
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
                  <th style={{ ...thStyle, textAlign: "left" }}>Sector</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Score</th>
                  <th style={{ ...thStyle, textAlign: "left", minWidth: 220 }}>Factor signals</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.ticker} className="qpl-row">
                    <td style={{ ...tdStyle, textAlign: "right", color: theme.color.faint, fontFamily: theme.font.mono }}>{item.rank}</td>
                    <td style={{ ...tdStyle, fontFamily: theme.font.mono, fontWeight: 600 }}>{item.ticker}</td>
                    <td style={tdStyle}>
                      {item.name}
                      {item.rationale && <div style={rationaleStyle}>{item.rationale}</div>}
                    </td>
                    <td style={{ ...tdStyle, color: theme.color.muted }}>{item.sector ?? "—"}</td>
                    <td style={{ ...tdStyle, textAlign: "right", fontFamily: theme.font.mono, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                      {num(item.score)}
                    </td>
                    <td style={tdStyle}>
                      <SignalBars signals={item.signals} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

/** Diverging mini-bars centered on zero: green = positive signal, red = negative. */
function SignalBars({ signals }: { signals: FactorSignal[] }) {
  const scale = 3; // clamp z-scores to ~[-3, 3]
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {signals.map((s) => {
        const clamped = Math.max(-scale, Math.min(scale, s.value));
        const widthPct = (Math.abs(clamped) / scale) * 50; // half-track each side
        const positive = clamped >= 0;
        return (
          <div key={s.name} style={signalRowStyle}>
            <span style={signalNameStyle}>{s.name}</span>
            <span style={signalTrackStyle}>
              <span style={signalAxisStyle} />
              <span
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  left: positive ? "50%" : `${50 - widthPct}%`,
                  width: `${widthPct}%`,
                  background: positive ? theme.color.positive : theme.color.negative,
                  borderRadius: 2,
                }}
              />
            </span>
            <span style={signalValueStyle}>{num(s.value, 1)}</span>
          </div>
        );
      })}
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
  verticalAlign: "top",
};
const rationaleStyle: CSSProperties = { marginTop: 2, fontSize: 12, color: theme.color.muted, maxWidth: 320 };
const emptyStyle: CSSProperties = { padding: 24, textAlign: "center", color: theme.color.muted, fontSize: 14 };
const signalRowStyle: CSSProperties = { display: "flex", alignItems: "center", gap: 8 };
const signalNameStyle: CSSProperties = { width: 78, fontSize: 11.5, color: theme.color.muted, textTransform: "capitalize" };
const signalTrackStyle: CSSProperties = { position: "relative", width: 120, height: 8, background: theme.color.grid, borderRadius: 2 };
const signalAxisStyle: CSSProperties = { position: "absolute", left: "50%", top: -1, bottom: -1, width: 1, background: theme.color.borderStrong };
const signalValueStyle: CSSProperties = {
  width: 36,
  textAlign: "right",
  fontFamily: theme.font.mono,
  fontVariantNumeric: "tabular-nums",
  fontSize: 12,
  color: theme.color.ink,
};
