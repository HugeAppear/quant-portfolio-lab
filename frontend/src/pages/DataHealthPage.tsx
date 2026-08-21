import { useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { api, useApi, usePollingApi } from "../api/client";
import { shortDate, theme } from "../theme";
import { Button, ErrorState, Loading, PageHeader, Panel, StatusBadge } from "../components/ui";
import type { DataHealthCheck, DataJob, DataLoadRequest, HealthStatus } from "../api/types";

const STATUS_ORDER: Record<HealthStatus, number> = { error: 0, warning: 1, ok: 2 };

export default function DataHealthPage() {
  const { data, error, loading, refetch } = useApi(() => api.getDataHealth());

  if (loading && !data) return <Loading label="Running data checks…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  const checks = [...(data?.checks ?? [])].sort(
    (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || a.source.localeCompare(b.source),
  );
  const counts = countBy(checks);

  return (
    <>
      <PageHeader
        title="Data health"
        description={
          data ? `Last checked ${shortDate(data.checkedAt)} · database: ${data.dbPath}` : undefined
        }
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
                    <td style={{ ...tdStyle, color: theme.color.muted, maxWidth: 320, whiteSpace: "normal" }}>
                      {c.message ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <DataLoadPanel onDataChanged={refetch} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Data loading (pykrx / FinanceDataReader -> DuckDB)
// ---------------------------------------------------------------------------

function DataLoadPanel({ onDataChanged }: { onDataChanged: () => void }) {
  const [kind, setKind] = useState<DataLoadRequest["kind"]>("all");
  const [start, setStart] = useState("2018-01-01");
  const [end, setEnd] = useState("");
  const [universeSize, setUniverseSize] = useState(100);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const jobs = usePollingApi(() => api.listDataJobs(), [], {
    active: (list) => (list ?? []).some((j) => j.status === "queued" || j.status === "running"),
    intervalMs: 2000,
  });

  const anyActive = (jobs.data ?? []).some((j) => j.status === "queued" || j.status === "running");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.startDataLoad({
        kind,
        start,
        end: end || null,
        universeSize,
        synthetic: false,
      });
      jobs.refetch();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to start the data load.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      title="Load real market data"
      subtitle="Pulls KRX prices/fundamentals via pykrx and benchmarks via FinanceDataReader into DuckDB. Requires the [data] extras and network access."
      style={{ marginTop: 18 }}
    >
      <form onSubmit={handleSubmit}>
        <div style={loadGrid}>
          <Field label="What to load">
            <select value={kind} onChange={(e) => setKind(e.target.value as DataLoadRequest["kind"])} style={inputStyle}>
              <option value="all">Prices + fundamentals</option>
              <option value="prices">Prices only</option>
              <option value="fundamentals">Fundamentals only</option>
            </select>
          </Field>
          <Field label="Start date">
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} style={inputStyle} required />
          </Field>
          <Field label="End date (optional)">
            <input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} style={inputStyle} />
          </Field>
          <Field label="Universe size">
            <input type="number" min={1} max={500} value={universeSize} onChange={(e) => setUniverseSize(Number(e.target.value))} style={inputStyle} />
          </Field>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <Button type="submit" disabled={submitting || anyActive}>
              {anyActive ? "Load in progress…" : submitting ? "Starting…" : "Start load"}
            </Button>
          </div>
        </div>
        {submitError && <div style={errorLineStyle}>{submitError}</div>}
      </form>

      {(jobs.data ?? []).length > 0 && (
        <div style={{ marginTop: 16 }}>
          {(jobs.data ?? []).slice(0, 3).map((job) => (
            <JobCard key={job.id} job={job} onCompleted={onDataChanged} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function JobCard({ job, onCompleted }: { job: DataJob; onCompleted: () => void }) {
  const [expanded, setExpanded] = useState(job.status === "running" || job.status === "queued");
  // Refresh the health table once when a job we watched finishes (jobs that
  // were already finished at mount don't re-trigger a refresh).
  const doneRef = useRef(job.status === "completed" || job.status === "failed");
  useEffect(() => {
    if ((job.status === "completed" || job.status === "failed") && !doneRef.current) {
      doneRef.current = true;
      onCompleted();
    }
  }, [job.status, onCompleted]);

  return (
    <div style={jobCardStyle}>
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
        onClick={() => setExpanded((v) => !v)}
      >
        <StatusBadge status={job.status === "completed" ? "ok" : job.status === "failed" ? "error" : "running"} />
        <span style={{ fontWeight: 600, fontSize: 13 }}>
          {job.kind === "all" ? "Prices + fundamentals" : job.kind}
        </span>
        <span style={{ color: theme.color.faint, fontSize: 12, fontFamily: theme.font.mono }}>
          {shortDate(job.createdAt)}
        </span>
        <span style={{ marginLeft: "auto", color: theme.color.faint, fontSize: 12 }}>
          {expanded ? "hide log" : "show log"}
        </span>
      </div>
      {job.error && <div style={errorLineStyle}>{job.error}</div>}
      {expanded && job.logTail.length > 0 && (
        <pre style={logStyle}>{job.logTail.join("\n")}</pre>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
      <span style={fieldLabelStyle}>{label}</span>
      {children}
    </label>
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

function fmtInt(v: number | null | undefined): string {
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
const loadGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
  gap: 14,
};
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
const errorLineStyle: CSSProperties = {
  marginTop: 10,
  padding: "10px 12px",
  borderRadius: theme.radius.sm,
  background: theme.color.negativeSoft,
  color: theme.color.negative,
  fontSize: 13,
};
const jobCardStyle: CSSProperties = {
  border: `1px solid ${theme.color.border}`,
  borderRadius: theme.radius.sm,
  padding: "10px 12px",
  marginTop: 8,
  background: theme.color.surfaceAlt,
};
const logStyle: CSSProperties = {
  marginTop: 8,
  marginBottom: 0,
  padding: "10px 12px",
  background: "#10151B",
  color: "#C8D0DA",
  borderRadius: theme.radius.sm,
  fontFamily: theme.font.mono,
  fontSize: 11.5,
  lineHeight: 1.5,
  maxHeight: 220,
  overflow: "auto",
  whiteSpace: "pre-wrap",
};
