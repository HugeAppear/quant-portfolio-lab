import { useEffect, useRef, useState } from "react";
import { api, useApi, usePollingApi } from "../api/client";
import { money, num, pct, signedPct, theme } from "../theme";
import {
  ACTIVE_RUN_STATUSES,
  dataModeLabel,
  strategyLabel,
  weightingLabel,
  type RunConfig,
  type RunStatus,
} from "../api/types";
import RunControls from "../components/RunControls";
import HoldingsTable from "../components/HoldingsTable";
import PlotlyChart, { buildDrawdownTrace, buildEquityTraces } from "../components/PlotlyChart";
import MetricCard from "../components/MetricCard";
import {
  ErrorState,
  Loading,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/ui";
import type { CSSProperties } from "react";

function fmtCreated(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

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
          {runs.loading && !runs.data ? (
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
                    <th style={{ ...thStyle, textAlign: "left" }}>Config</th>
                    <th style={{ ...thStyle, textAlign: "left" }}>Data</th>
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
                        <td style={{ ...tdStyle, fontFamily: theme.font.mono, fontSize: 12.5 }}>{fmtCreated(r.createdAt)}</td>
                        <td style={tdStyle}>{strategyLabel(r.strategy)}</td>
                        <td style={{ ...tdStyle, color: theme.color.muted, fontSize: 12.5 }}>
                          {r.rebalance} · top {r.topN} · {weightingLabel(r.weighting)}
                        </td>
                        <td style={{ ...tdStyle, color: theme.color.muted, fontSize: 12.5 }}>{dataModeLabel(r.dataModeUsed)}</td>
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

      {selectedId && <RunDetail id={selectedId} onStatusSettled={runs.refetch} />}
    </>
  );
}

function isActiveStatus(status: RunStatus | undefined): boolean {
  return status !== undefined && ACTIVE_RUN_STATUSES.includes(status);
}

function RunDetail({ id, onStatusSettled }: { id: string; onStatusSettled: () => void }) {
  const { data: run, error, loading, refetch } = usePollingApi(
    () => api.getRun(id),
    [id],
    { active: (r) => isActiveStatus(r?.status) },
  );

  // When a watched run reaches a terminal state, refresh the history table so
  // its status badge and metrics update too.
  const prevStatus = useRef<RunStatus | null>(null);
  useEffect(() => {
    const status = run?.status ?? null;
    if (
      prevStatus.current !== null &&
      isActiveStatus(prevStatus.current) &&
      status !== null &&
      !isActiveStatus(status)
    ) {
      onStatusSettled();
    }
    prevStatus.current = status;
  }, [run?.status, onStatusSettled]);

  const equity = run?.equityCurve ?? [];
  const m = run?.metrics;

  return (
    <div style={{ marginTop: 18 }}>
      <Panel
        title="Run detail"
        subtitle={
          run
            ? `${strategyLabel(run.strategy)} · ${run.rebalance} · top ${run.topN} · ${weightingLabel(run.weighting)} · ${dataModeLabel(run.dataModeUsed)}`
            : id
        }
        actions={run ? <StatusBadge status={run.status} /> : undefined}
      >
        {loading && !run ? (
          <Loading label="Loading run…" />
        ) : error ? (
          <ErrorState error={error} onRetry={refetch} />
        ) : run?.status === "failed" ? (
          <div style={errorLineStyle}>{run.error ?? "This run failed."}</div>
        ) : run && isActiveStatus(run.status) ? (
          <Loading label={run.status === "queued" ? "Queued — waiting for the engine…" : "Backtest running…"} />
        ) : m ? (
          <>
            <div style={detailMetricGrid}>
              <MetricCard label="Total return" value={signedPct(m.totalReturn)} numericValue={m.totalReturn ?? undefined} intent="auto" />
              <MetricCard label="CAGR" value={signedPct(m.cagr)} numericValue={m.cagr ?? undefined} intent="auto" />
              <MetricCard label="Excess CAGR" value={signedPct(m.excessCagr)} numericValue={m.excessCagr ?? undefined} intent="auto" />
              <MetricCard label="Sharpe" value={num(m.sharpe)} />
              <MetricCard label="Max drawdown" value={pct(m.maxDrawdown)} intent="negative" />
              <MetricCard label="Volatility" value={pct(m.volatility)} />
              <MetricCard label="Final value" value={money(m.finalValue, true)} />
            </div>
            {equity.length ? (
              <div style={{ marginTop: 16 }}>
                <PlotlyChart data={buildEquityTraces(equity)} height={300} />
                <PlotlyChart data={buildDrawdownTrace(equity)} height={180} />
              </div>
            ) : null}
            {run?.holdings?.length ? (
              <div style={{ marginTop: 16 }}>
                <HoldingsTable holdings={run.holdings} maxRows={12} />
              </div>
            ) : null}
          </>
        ) : (
          <div style={emptyLineStyle}>This run is {run?.status ?? "pending"} — no metrics to show.</div>
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
