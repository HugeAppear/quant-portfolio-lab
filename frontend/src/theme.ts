// Shared design tokens and number formatters.
// A quant dashboard lives or dies on legible numbers, so figures are mono +
// tabular and gains/losses get a consistent semantic color.

export const theme = {
  color: {
    bg: "#F5F7F9",
    surface: "#FFFFFF",
    surfaceAlt: "#FAFBFC",
    border: "#E4E8EC",
    borderStrong: "#CDD5DD",
    ink: "#10151B",
    muted: "#5A6573",
    faint: "#8A93A1",
    accent: "#3551E5",
    accentSoft: "#EDF0FE",
    positive: "#137A52",
    positiveSoft: "#E5F4EC",
    negative: "#C53434",
    negativeSoft: "#FBEBEB",
    warning: "#B5790E",
    warningSoft: "#FAF1DD",
    grid: "#EDF0F3",
  },
  font: {
    sans: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    mono: "'JetBrains Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace",
  },
  radius: { sm: 6, md: 10, lg: 14 },
  shadow: {
    sm: "0 1px 2px rgba(16, 21, 27, 0.05)",
    md: "0 4px 16px rgba(16, 21, 27, 0.06)",
  },
} as const;

// Reusable inline-style snippet for numeric cells/values.
export const mono = {
  fontFamily: theme.font.mono,
  fontVariantNumeric: "tabular-nums",
} as const;

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Fraction -> percent string. 0.1234 -> "12.34%". */
export function pct(v: number | null | undefined, digits = 2): string {
  return isNum(v) ? `${(v * 100).toFixed(digits)}%` : "—";
}

/** Like pct but with an explicit leading sign for positives. */
export function signedPct(v: number | null | undefined, digits = 2): string {
  if (!isNum(v)) return "—";
  const s = `${(v * 100).toFixed(digits)}%`;
  return v > 0 ? `+${s}` : s;
}

export function num(v: number | null | undefined, digits = 2): string {
  return isNum(v) ? v.toFixed(digits) : "—";
}

const moneyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const moneyCompactFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function money(v: number | null | undefined, compact = false): string {
  if (!isNum(v)) return "—";
  return (compact ? moneyCompactFmt : moneyFmt).format(v);
}

/** Color for a signed value: green up, red down, ink at zero/non-numeric. */
export function signColor(v: number | null | undefined): string {
  if (!isNum(v) || v === 0) return theme.color.ink;
  return v > 0 ? theme.color.positive : theme.color.negative;
}

/** Short, human date for axis labels and tables. "2024-03-01" -> "Mar 1, 2024". */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}
