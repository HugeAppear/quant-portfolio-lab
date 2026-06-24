import type { CSSProperties } from "react";
import { api, useApi } from "../api/client";
import { shortDate } from "../theme";
import { theme } from "../theme";
import { Button, ErrorState, Loading, PageHeader, Panel, StatusBadge } from "../components/ui";
import type { DataHealthCheck, HealthStatus } from "../api/types";

const STATUS_ORDER: Record<HealthStatus, number> = { error: 0, warning: 1, ok: 2 };

export default function DataHealthPage() {
  const { data, error, loading, refetch } = useApi(() => api.getDataHealth());

  if (loading) return <Loading label="Running data checks…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  const checks = [...(data?.checks ?? [])].sort(
    (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || a.source.localeCompare(b.source),
  );
  const counts = countBy(checks);

  return (
    <>
      <PageHeader
        title="Data health"
        description={data ? `Last checked ${shortDate(data.checkedAt)}` : undefined}
        actions={<Button variant="ghost" onClick={refetch}>Re-check</Button>}
      />

      <div style={summaryRow}>
        <SummaryStat label="Sources" value={checks.length} color={theme.color.ink} />
        <SummaryStat label="OK" value={counts.ok} color={theme.color.positive} />
        <SummaryStat label="Warnings" value={counts.warning} color={theme.color.warning} />
        <SummaryStat label="Errors" value={counts.error} color={theme.color.negative} />
      </div>

      <Panel title="Sources" padding={0} style={{ marginTop: 18 }}>
        {checks.length === 0 ? (
          <div style={emptyStyle}>No data sources are being tracked.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: "left" }}>Source</th>
                  <th style={{ ...thStyle, textAlign: "left" }}>Status</th>
                  <th style={{ ...thStyle, textAlign: "left" }}>Last updated</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Symbols</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Rows</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Missing</th>
                  <th style={{ ...thStyle, textAlign: "left" }}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {checks.map((c) => (
                  <tr key={c.source} className="qpl-row">
                    <td style={{ ...tdStyle, fontWeight: 600 }}>{c.source}</td>
                    <td style={tdStyle}><StatusBadge status={c.status} /></td>
                    <td style={{ ...tdStyle, color: theme.color.muted }}>
                      {shortDate(c.lastUpdated)}
                      {typeof c.staleDays === "number" && c.staleDays > 0 && (
                        <span style={{ color: theme.color.warning }}> · {c.staleDays}d stale</span>
                      )}
                    </td>
                    <td style={numTd}>{fmtInt(c.symbols)}</td>
                    <td style={numTd}>{fmtInt(c.rows)}</td>
                    <td style={{ ...numTd, color: c.missingSessions ? theme.color.warning : theme.color.muted }}>
                      {fmtInt(c.missingSessions)}
                    </td>
                    <td style={{ ...tdStyle, color: theme.color.muted, maxWidth: 280, whiteSpace: "normal" }}>
                      {c.message ?? "—"}
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

function SummaryStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={summaryCard}>
      <div style={{ fontFamily: theme.font.mono, fontSize: 28, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      <div style={summaryLabel}>{label}</div>
    </div>
  );
}

function countBy(checks: DataHealthCheck[]) {
  return checks.reduce(
    (acc, c) => {
      acc[c.status] += 1;
      return acc;
    },
    { ok: 0, warning: 0, error: 0 } as Record<HealthStatus, number>,
  );
}

function fmtInt(v: number | undefined): string {
  return typeof v === "number" ? v.toLocaleString("en-US") : "—";
}

const summaryRow: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: 12,
};
const summaryCard: CSSProperties = {
  background: theme.color.surface,
  border: `1px solid ${theme.color.border}`,
  borderRadius: theme.radius.md,
  padding: "14px 16px",
};
const summaryLabel: CSSProperties = {
  marginTop: 4,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: theme.color.faint,
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
const emptyStyle: CSSProperties = { padding: 24, textAlign: "center", color: theme.color.muted, fontSize: 14 };
