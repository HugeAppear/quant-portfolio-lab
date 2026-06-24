import { useState } from "react";
import { api, useApi } from "../api/client";
import { num, pct, signedPct, shortDate } from "../theme";
import { strategyLabel, universeLabel } from "../api/types";
import { theme } from "../theme";
import RunControls from "../components/RunControls";
import PlotlyChart, { buildEquityTraces } from "../components/PlotlyChart";
import MetricCard from "../components/MetricCard";
import {
  ErrorState,
  Loading,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/ui";
import type { CSSProperties } from "react";
import type { RunConfig } from "../api/types";

export default function RunsPage() {
  const runs = useApi(() => api.listRuns());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = async (config: RunConfig) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createRun(config);
      setSelectedId(created.id);
      runs.refetch();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to start run.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <PageHeader title="Runs" description="Configure and launch backtests, then compare results." />

      <Panel title="New backtest" subtitle="Parameters feed straight into the engine">
        <RunControls onSubmit={handleSubmit} submitting={submitting} />
        {submitError && <div style={errorLineStyle}>{submitError}</div>}
      </Panel>

      <div style={{ marginTop: 18 }}>
        <Panel title="History" subtitle="Select a run to inspect it" padding={0}>
          {runs.loading ? (
            <Loading label="Loading runs…" />
          ) : runs.error ? (
            <ErrorState error={runs.error} onRetry={runs.refetch} />
          ) : !runs.data || runs.data.length === 0 ? (
            <div style={emptyLineStyle}>No runs yet — launch one above.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={{ ...thStyle, textAlign: "left" }}>Created</th>
                    <th style={{ ...thStyle, textAlign: "left" }}>Strategy</th>
                    <th style={{ ...thStyle, textAlign: "left" }}>Universe</th>
                    <th style={{ ...thStyle, textAlign: "left" }}>Status</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>CAGR</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Sharpe</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Max DD</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.map((r) => {
                    const active = r.id === selectedId;
                    return (
                      <tr
                        key={r.id}
                        className="qpl-row"
                        onClick={() => setSelectedId(active ? null : r.id)}
                        style={{ cursor: "pointer", background: active ? theme.color.accentSoft : undefined }}
                      >
                        <td style={{ ...tdStyle, fontFamily: theme.font.mono, fontSize: 12.5 }}>{shortDate(r.createdAt)}</td>
                        <td style={tdStyle}>{strategyLabel(r.strategy)}</td>
                        <td style={{ ...tdStyle, color: theme.color.muted }}>{universeLabel(r.universe)}</td>
                        <td style={tdStyle}><StatusBadge status={r.status} /></td>
                        <td style={numTd}>{signedPct(r.metrics?.cagr)}</td>
                        <td style={numTd}>{num(r.metrics?.sharpe)}</td>
                        <td style={numTd}>{pct(r.metrics?.maxDrawdown)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      {selectedId && <RunDetail id={selectedId} />}
    </>
  );
}

function RunDetail({ id }: { id: string }) {
  const { data: run, error, loading, refetch } = useApi(() => api.getRun(id), [id]);

  return (
    <div style={{ marginTop: 18 }}>
      <Panel title="Run detail" subtitle={run ? `${strategyLabel(run.strategy)} · ${shortDate(run.config.startDate)} – ${shortDate(run.config.endDate)}` : id}>
        {loading ? (
          <Loading label="Loading run…" />
        ) : error ? (
          <ErrorState error={error} onRetry={refetch} />
        ) : run?.status === "failed" ? (
          <div style={errorLineStyle}>{run.error ?? "This run failed."}</div>
        ) : run?.metrics ? (
          <>
            <div style={detailMetricGrid}>
              <MetricCard label="Total return" value={signedPct(run.metrics.totalReturn)} numericValue={run.metrics.totalReturn} intent="auto" />
              <MetricCard label="CAGR" value={signedPct(run.metrics.cagr)} numericValue={run.metrics.cagr} intent="auto" />
              <MetricCard label="Sharpe" value={num(run.metrics.sharpe)} />
              <MetricCard label="Max drawdown" value={pct(run.metrics.maxDrawdown)} intent="negative" />
              <MetricCard label="Volatility" value={pct(run.metrics.volatility)} />
            </div>
            {run.equityCurve?.length ? (
              <div style={{ marginTop: 16 }}>
                <PlotlyChart data={buildEquityTraces(run.equityCurve)} height={300} />
              </div>
            ) : null}
          </>
        ) : (
          <div style={emptyLineStyle}>This run is still {run?.status ?? "pending"}.</div>
        )}
      </Panel>
    </div>
  );
}

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
const detailMetricGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
  gap: 12,
};
const errorLineStyle: CSSProperties = {
  marginTop: 12,
  padding: "10px 12px",
  borderRadius: theme.radius.sm,
  background: theme.color.negativeSoft,
  color: theme.color.negative,
  fontSize: 13,
};
const emptyLineStyle: CSSProperties = { padding: 24, textAlign: "center", color: theme.color.muted, fontSize: 14 };
