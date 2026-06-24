import type { CSSProperties, ReactNode } from "react";
import { theme } from "../theme";

type Intent = "auto" | "positive" | "negative" | "neutral";

interface MetricCardProps {
  label: string;
  /** Pre-formatted display value (string) or any node. */
  value: ReactNode;
  /** Raw numeric value used only when intent="auto" to pick the color. */
  numericValue?: number;
  intent?: Intent;
  hint?: string;
  loading?: boolean;
}

function resolveColor(intent: Intent, numericValue?: number): string {
  switch (intent) {
    case "positive":
      return theme.color.positive;
    case "negative":
      return theme.color.negative;
    case "neutral":
      return theme.color.ink;
    case "auto":
    default:
      if (typeof numericValue !== "number" || !Number.isFinite(numericValue)) return theme.color.ink;
      if (numericValue > 0) return theme.color.positive;
      if (numericValue < 0) return theme.color.negative;
      return theme.color.ink;
  }
}

export default function MetricCard({
  label,
  value,
  numericValue,
  intent = "neutral",
  hint,
  loading,
}: MetricCardProps) {
  return (
    <div style={cardStyle}>
      <div style={labelStyle}>{label}</div>
      <div
        style={{
          ...valueStyle,
          color: loading ? theme.color.faint : resolveColor(intent, numericValue),
        }}
      >
        {loading ? "···" : value}
      </div>
      {hint ? <div style={hintStyle}>{hint}</div> : null}
    </div>
  );
}

const cardStyle: CSSProperties = {
  background: theme.color.surface,
  border: `1px solid ${theme.color.border}`,
  borderRadius: theme.radius.md,
  padding: "15px 17px",
  display: "flex",
  flexDirection: "column",
  gap: 7,
  minWidth: 0,
};
const labelStyle: CSSProperties = {
  fontFamily: theme.font.sans,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: theme.color.faint,
};
const valueStyle: CSSProperties = {
  fontFamily: theme.font.mono,
  fontSize: 25,
  fontWeight: 600,
  fontVariantNumeric: "tabular-nums",
  lineHeight: 1.1,
  letterSpacing: "-0.01em",
};
const hintStyle: CSSProperties = {
  fontFamily: theme.font.sans,
  fontSize: 12,
  color: theme.color.muted,
};
