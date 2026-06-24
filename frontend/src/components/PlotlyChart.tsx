// Themed wrapper around react-plotly.js plus a few trace builders that turn our
// domain types into Plotly traces. Requires: plotly.js, react-plotly.js
// (+ @types/plotly.js, @types/react-plotly.js).

import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { Config, Data, Layout } from "plotly.js";
import { theme } from "../theme";
import type { AllocationPoint, EquityPoint } from "../api/types";

interface PlotlyChartProps {
  data: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  height?: number;
}

const baseLayout: Partial<Layout> = {
  font: { family: theme.font.sans, size: 12, color: theme.color.muted },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { l: 58, r: 16, t: 12, b: 36 },
  hovermode: "x unified",
  legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11 } },
  xaxis: {
    gridcolor: theme.color.grid,
    linecolor: theme.color.border,
    zeroline: false,
    tickfont: { family: theme.font.mono, size: 10 },
  },
  yaxis: {
    gridcolor: theme.color.grid,
    linecolor: theme.color.border,
    zeroline: false,
    tickfont: { family: theme.font.mono, size: 10 },
  },
};

const baseConfig: Partial<Config> = { displayModeBar: false, responsive: true };

export default function PlotlyChart({ data, layout, config, height = 320 }: PlotlyChartProps) {
  const mergedLayout = useMemo<Partial<Layout>>(
    () => ({
      ...baseLayout,
      ...layout,
      height,
      xaxis: { ...baseLayout.xaxis, ...(layout?.xaxis ?? {}) },
      yaxis: { ...baseLayout.yaxis, ...(layout?.yaxis ?? {}) },
      legend: { ...baseLayout.legend, ...(layout?.legend ?? {}) },
    }),
    [layout, height],
  );

  return (
    <Plot
      data={data}
      layout={mergedLayout}
      config={{ ...baseConfig, ...config }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}

// ---------------------------------------------------------------------------
// Trace builders
// ---------------------------------------------------------------------------

export function buildEquityTraces(equity: EquityPoint[]): Data[] {
  const x = equity.map((p) => p.date);
  const traces: Data[] = [
    {
      x,
      y: equity.map((p) => p.equity),
      type: "scatter",
      mode: "lines",
      name: "Strategy",
      line: { color: theme.color.accent, width: 2 },
      fill: "tozeroy",
      fillcolor: "rgba(53, 81, 229, 0.06)",
    },
  ];
  if (equity.some((p) => typeof p.benchmark === "number")) {
    traces.push({
      x,
      y: equity.map((p) => (typeof p.benchmark === "number" ? p.benchmark : null)),
      type: "scatter",
      mode: "lines",
      name: "Benchmark",
      line: { color: theme.color.faint, width: 1.5, dash: "dot" },
    });
  }
  return traces;
}

export function buildDrawdownTrace(equity: EquityPoint[]): Data[] {
  return [
    {
      x: equity.map((p) => p.date),
      y: equity.map((p) => (typeof p.drawdown === "number" ? p.drawdown * 100 : null)),
      type: "scatter",
      mode: "lines",
      name: "Drawdown",
      line: { color: theme.color.negative, width: 1 },
      fill: "tozeroy",
      fillcolor: "rgba(197, 52, 52, 0.08)",
    },
  ];
}

/**
 * Stacked-area allocation over time. Keeps the top-N tickers by average weight
 * and rolls the remainder into an "Other" band to stay readable.
 */
export function buildAllocationTraces(allocation: AllocationPoint[], topN = 12): Data[] {
  if (allocation.length === 0) return [];

  const totals = new Map<string, number>();
  for (const point of allocation) {
    for (const [ticker, weight] of Object.entries(point.weights)) {
      totals.set(ticker, (totals.get(ticker) ?? 0) + weight);
    }
  }
  const ordered = [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t);
  const top = ordered.slice(0, topN);
  const rest = ordered.slice(topN);
  const x = allocation.map((p) => p.date);
  const palette = allocationPalette(top.length);

  const traces: Data[] = top.map((ticker, i) => ({
    x,
    y: allocation.map((p) => (p.weights[ticker] ?? 0) * 100),
    type: "scatter",
    mode: "lines",
    name: ticker,
    stackgroup: "alloc",
    line: { width: 0.5, color: palette[i] },
    fillcolor: palette[i],
  }));

  if (rest.length) {
    traces.push({
      x,
      y: allocation.map((p) => rest.reduce((s, t) => s + (p.weights[t] ?? 0), 0) * 100),
      type: "scatter",
      mode: "lines",
      name: "Other",
      stackgroup: "alloc",
      line: { width: 0.5, color: theme.color.borderStrong },
      fillcolor: theme.color.borderStrong,
    });
  }
  return traces;
}

function allocationPalette(n: number): string[] {
  const base = [
    "#3551E5", "#2E8B8B", "#9B6CD6", "#C58A1B", "#3E9C6B", "#D06A8C",
    "#5A7BD6", "#B5793E", "#6BA84F", "#C5544E", "#7A8190", "#4FA3C7",
  ];
  return Array.from({ length: n }, (_, i) => base[i % base.length]);
}
