import { Link } from "react-router-dom";
import { api, useApi } from "../api/client";
import { pct, num, signedPct, shortDate } from "../theme";
import { strategyLabel, universeLabel } from "../api/types";
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

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={
          <>
            {strategyLabel(run.strategy)} · {universeLabel(run.universe)} ·{" "}
            {shortDate(run.config.startDate)} – {shortDate(run.config.endDate)}
          </>
        }
        actions={<StatusBadge status={run.status} />}
      />

      <div style={metricGrid}>
        <MetricCard label="Total return" value={signedPct(m?.totalReturn)} numericValue={m?.totalReturn} intent="auto" />
        <MetricCard label="CAGR" value={signedPct(m?.cagr)} numericValue={m?.cagr} intent="auto" />
        <MetricCard label="Sharpe" value={num(m?.sharpe)} intent="neutral" />
        <MetricCard label="Sortino" value={num(m?.sortino)} intent="neutral" />
        <MetricCard label="Max drawdown" value={pct(m?.maxDrawdown)} intent="negative" />
        <MetricCard label="Volatility" value={pct(m?.volatility)} intent="neutral" />
        <MetricCard label="Calmar" value={num(m?.calmar)} intent="neutral" />
        <MetricCard label="Turnover" value={pct(m?.turnover, 0)} intent="neutral" hint="annualized" />
      </div>

      <div style={{ marginTop: 18 }}>
        <Panel title="Equity curve" subtitle="Strategy value vs. benchmark over the test period">
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
        <Panel title="Allocation over time" subtitle="Portfolio weights by name (%)">
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
          title="Current holdings"
          subtitle={`${holdings.length} positions · as of ${shortDate(run.config.endDate)}`}
          padding={0}
        >
          <HoldingsTable holdings={holdings} maxRows={15} />
        </Panel>
      </div>

      <p style={footnote}>
        Backtested results are gross of taxes and exclude market impact beyond the modeled{" "}
        {num(run.config.transactionCostBps, 1)} bps cost / {num(run.config.slippageBps, 1)} bps slippage.
        Live performance typically diverges from backtests.
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
