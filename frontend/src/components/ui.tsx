// Small, dependency-free UI primitives shared across pages.
import type { CSSProperties, ReactNode } from "react";
import { theme } from "../theme";
import type { HealthStatus, RunStatus } from "../api/types";

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

export function Panel({
  title,
  subtitle,
  actions,
  children,
  padding = 18,
  style,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  padding?: number;
  style?: CSSProperties;
}) {
  return (
    <section style={{ ...panelStyle, ...style }}>
      {(title || actions) && (
        <header style={panelHeaderStyle}>
          <div style={{ minWidth: 0 }}>
            {title && <h2 style={panelTitleStyle}>{title}</h2>}
            {subtitle && <p style={panelSubtitleStyle}>{subtitle}</p>}
          </div>
          {actions && <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>{actions}</div>}
        </header>
      )}
      <div style={{ padding }}>{children}</div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// PageHeader
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div style={pageHeaderStyle}>
      <div style={{ minWidth: 0 }}>
        <h1 style={pageTitleStyle}>{title}</h1>
        {description && <p style={pageDescStyle}>{description}</p>}
      </div>
      {actions && <div style={{ display: "flex", gap: 8 }}>{actions}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

type AnyStatus = RunStatus | HealthStatus | string;

const STATUS_TONE: Record<string, { fg: string; bg: string; label?: string }> = {
  // run statuses
  completed: { fg: theme.color.positive, bg: theme.color.positiveSoft },
  running: { fg: theme.color.accent, bg: theme.color.accentSoft },
  queued: { fg: theme.color.muted, bg: theme.color.surfaceAlt },
  failed: { fg: theme.color.negative, bg: theme.color.negativeSoft },
  // health statuses
  ok: { fg: theme.color.positive, bg: theme.color.positiveSoft },
  warning: { fg: theme.color.warning, bg: theme.color.warningSoft },
  error: { fg: theme.color.negative, bg: theme.color.negativeSoft },
};

export function StatusBadge({ status }: { status: AnyStatus }) {
  const tone = STATUS_TONE[status] ?? { fg: theme.color.muted, bg: theme.color.surfaceAlt };
  return (
    <span style={{ ...badgeStyle, color: tone.fg, background: tone.bg }}>
      <span style={{ ...dotStyle, background: tone.fg }} />
      {tone.label ?? status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Buttons
// ---------------------------------------------------------------------------

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const base = variant === "primary" ? primaryButton : ghostButton;
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="qpl-btn"
      style={{ ...base, opacity: disabled ? 0.55 : 1, cursor: disabled ? "not-allowed" : "pointer" }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// State views
// ---------------------------------------------------------------------------

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div style={stateBoxStyle}>
      <span className="qpl-spinner" style={spinnerStyle} />
      <span style={{ color: theme.color.muted, fontSize: 14 }}>{label}</span>
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error | null;
  onRetry?: () => void;
}) {
  return (
    <div style={{ ...stateBoxStyle, flexDirection: "column", gap: 12 }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontWeight: 600, color: theme.color.ink, marginBottom: 4 }}>
          Something went wrong
        </div>
        <div style={{ color: theme.color.muted, fontSize: 14, maxWidth: 460 }}>
          {error?.message ?? "Unexpected error."}
        </div>
      </div>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div style={{ ...stateBoxStyle, flexDirection: "column", gap: 10 }}>
      <div style={{ fontWeight: 600, color: theme.color.ink }}>{title}</div>
      {hint && (
        <div style={{ color: theme.color.muted, fontSize: 14, textAlign: "center", maxWidth: 440 }}>
          {hint}
        </div>
      )}
      {action}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const panelStyle: CSSProperties = {
  background: theme.color.surface,
  border: `1px solid ${theme.color.border}`,
  borderRadius: theme.radius.lg,
  boxShadow: theme.shadow.sm,
  overflow: "hidden",
};
const panelHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 12,
  padding: "14px 18px",
  borderBottom: `1px solid ${theme.color.border}`,
};
const panelTitleStyle: CSSProperties = {
  margin: 0,
  fontFamily: theme.font.sans,
  fontSize: 14,
  fontWeight: 600,
  color: theme.color.ink,
  letterSpacing: "-0.01em",
};
const panelSubtitleStyle: CSSProperties = {
  margin: "2px 0 0",
  fontSize: 12.5,
  color: theme.color.muted,
};
const pageHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-end",
  justifyContent: "space-between",
  gap: 16,
  marginBottom: 20,
};
const pageTitleStyle: CSSProperties = {
  margin: 0,
  fontFamily: theme.font.sans,
  fontSize: 22,
  fontWeight: 700,
  letterSpacing: "-0.02em",
  color: theme.color.ink,
};
const pageDescStyle: CSSProperties = {
  margin: "4px 0 0",
  fontSize: 13.5,
  color: theme.color.muted,
};
const badgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "2px 9px",
  borderRadius: 999,
  fontFamily: theme.font.sans,
  fontSize: 11.5,
  fontWeight: 600,
  textTransform: "capitalize",
  whiteSpace: "nowrap",
};
const dotStyle: CSSProperties = { width: 6, height: 6, borderRadius: 999 };
const primaryButton: CSSProperties = {
  appearance: "none",
  border: "none",
  background: theme.color.accent,
  color: "#fff",
  fontFamily: theme.font.sans,
  fontSize: 13,
  fontWeight: 600,
  padding: "9px 16px",
  borderRadius: theme.radius.sm,
};
const ghostButton: CSSProperties = {
  appearance: "none",
  background: theme.color.surface,
  color: theme.color.ink,
  border: `1px solid ${theme.color.borderStrong}`,
  fontFamily: theme.font.sans,
  fontSize: 13,
  fontWeight: 600,
  padding: "9px 16px",
  borderRadius: theme.radius.sm,
};
const stateBoxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 12,
  minHeight: 220,
  padding: 32,
};
const spinnerStyle: CSSProperties = {
  width: 18,
  height: 18,
  border: `2px solid ${theme.color.border}`,
  borderTopColor: theme.color.accent,
  borderRadius: "50%",
  display: "inline-block",
};
