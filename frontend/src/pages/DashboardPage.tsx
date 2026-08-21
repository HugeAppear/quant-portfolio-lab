import { Link } from "react-router-dom";
import { api, useApi } from "../api/client";
import { money, num, pct, shortDate, signedPct } from "../theme";
import { dataModeLabel, strategyLabel, weightingLabel } from "../api/types";
import MetricCard from "../components/MetricCard";
import HoldingsTable from "../components/HoldingsTable";
import PlotlyChart, {
  buildAllocationTraces,
  buildDrawdownTrace,
  buildEquityTraces,
} from "../components/PlotlyChart";
import {
  Button,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/ui";

export default function DashboardPage() {
  const { data, error, loading, refetch } = useApi(() => api.getDashboard());

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  const run = data?.latestRun;
  if (!run) {
    return (
      <>
        <PageHeader title="Dashboard" description="Overview of your most recent backtest." />
        <Panel padding={0}>
          <EmptyState
            title="No completed runs yet"
            hint="Launch your first backtest to see equity curves, drawdowns, and allocations here."
            action={
              <Link to="/runs" style={{ textDecoration: "none" }}>
                <Button>Go to Runs</Button>
              </Link>
            }
          />
        </Panel>
      </>
    );
  }

  const m = run.metrics;
  const equity = run.equityCurve ?? [];
  const allocation = run.allocation ?? [];
  const holdings = run.holdings ?? [];
  const firstDate = equity[0]?.date;
  const lastDate = equity[equity.length - 1]?.date;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={
          <>
            {strategyLabel(run.strategy)} · {run.rebalance} rebalance · top {run.topN} ·{" "}
            {weightingLabel(run.weighting)} · {dataModeLabel(run.dataModeUsed)} ·{" "}
            {shortDate(firstDate)} – {shortDate(lastDate)}
          </>
        }
        actions={<StatusBadge status={run.status} />}
      />

      <div style={metricGrid}>
        <MetricCard label="Total return" value={signedPct(m?.totalReturn)} numericValue={m?.totalReturn ?? undefined} intent="auto" />
        <MetricCard label="CAGR" value={signedPct(m?.cagr)} numericValue={m?.cagr ?? undefined} intent="auto" />
        <MetricCard label="Excess CAGR" value={signedPct(m?.excessCagr)} numericValue={m?.excessCagr ?? undefined} intent="auto" hint="vs benchmark" />
        <MetricCard label="Sharpe" value={num(m?.sharpe)} intent="neutral" />
        <MetricCard label="Sortino" value={num(m?.sortino)} intent="neutral" />
        <MetricCard label="Max drawdown" value={pct(m?.maxDrawdown)} intent="negative" />
        <MetricCard label="Volatility" value={pct(m?.volatility)} intent="neutral" />
        <MetricCard label="Calmar" value={num(m?.calmar)} intent="neutral" />
        <MetricCard label="Turnover" value={pct(m?.turnover, 0)} intent="neutral" hint="avg per rebalance" />
        <MetricCard label="Final value" value={money(m?.finalValue, true)} intent="neutral" />
      </div>

      <div style={{ marginTop: 18 }}>
        <Panel title="Equity curve" subtitle="Strategy value vs. benchmark (rebased to the same starting capital)">
          {equity.length ? (
            <PlotlyChart data={buildEquityTraces(equity)} height={360} />
          ) : (
            <NoSeries />
          )}
        </Panel>
      </div>

      <div style={twoCol}>
        <Panel title="Drawdown" subtitle="Peak-to-trough decline (%)">
          {equity.some((p) => typeof p.drawdown === "number") ? (
            <PlotlyChart data={buildDrawdownTrace(equity)} height={260} />
          ) : (
            <NoSeries />
          )}
        </Panel>
        <Panel title="Allocation at each rebalance" subtitle="Portfolio weights by name (%)">
          {allocation.length ? (
            <PlotlyChart
              data={buildAllocationTraces(allocation)}
              height={260}
              layout={{ yaxis: { ticksuffix: "%", rangemode: "tozero" } }}
            />
          ) : (
            <NoSeries />
          )}
        </Panel>
      </div>

      <div style={{ marginTop: 18 }}>
        <Panel
          title="Final holdings"
          subtitle={`${holdings.length} positions · as of the last rebalance`}
          padding={0}
        >
          <HoldingsTable holdings={holdings} maxRows={15} />
        </Panel>
      </div>

      <p style={footnote}>
        Costs modeled: {num(run.config.feeBps, 1)} bps fee, {num(run.config.taxBps, 1)} bps sell tax,{" "}
        {num(run.config.slippageBps, 1)} bps slippage. Backtested results are research output only —
        live performance typically diverges from backtests. Not investment advice.
      </p>
    </>
  );
}

function NoSeries() {
  return <div style={{ padding: 28, textAlign: "center", color: "#8A93A1", fontSize: 14 }}>No series data returned for this run.</div>;
}

const metricGrid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(165px, 1fr))",
  gap: 12,
};
const twoCol: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
  gap: 18,
  marginTop: 18,
};
const footnote: React.CSSProperties = {
  marginTop: 18,
  fontSize: 12,
  color: "#8A93A1",
  lineHeight: 1.5,
};
