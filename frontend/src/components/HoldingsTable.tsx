import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { money, pct, theme } from "../theme";
import type { Holding } from "../api/types";

type SortKey = "weight" | "ticker" | "value";

interface HoldingsTableProps {
  holdings: Holding[];
  maxRows?: number;
}

export default function HoldingsTable({ holdings, maxRows }: HoldingsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("weight");
  const [asc, setAsc] = useState(false);

  const rows = useMemo(() => {
    const sorted = [...holdings].sort((a, b) => {
      let d = 0;
      if (sortKey === "ticker") d = a.ticker.localeCompare(b.ticker);
      else if (sortKey === "value") d = (a.value ?? 0) - (b.value ?? 0);
      else d = a.weight - b.weight;
      return asc ? d : -d;
    });
    return maxRows ? sorted.slice(0, maxRows) : sorted;
  }, [holdings, sortKey, asc, maxRows]);

  const maxWeight = Math.max(...holdings.map((h) => h.weight), 0.0001);

  const toggle = (key: SortKey) => {
    if (key === sortKey) {
      setAsc((v) => !v);
    } else {
      setSortKey(key);
      setAsc(key === "ticker"); // names ascend by default, numbers descend
    }
  };

  if (holdings.length === 0) {
    return <div style={emptyStyle}>No holdings to show.</div>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={tableStyle}>
        <thead>
          <tr>
            <SortHeader label="Ticker" active={sortKey === "ticker"} asc={asc} onClick={() => toggle("ticker")} />
            <th style={{ ...thStyle, textAlign: "left" }}>Name</th>
            <th style={{ ...thStyle, textAlign: "left" }}>Sector</th>
            <SortHeader label="Weight" align="right" active={sortKey === "weight"} asc={asc} onClick={() => toggle("weight")} />
            <SortHeader label="Value" align="right" active={sortKey === "value"} asc={asc} onClick={() => toggle("value")} />
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.ticker} className="qpl-row">
              <td style={{ ...tdStyle, fontFamily: theme.font.mono, fontWeight: 600 }}>{h.ticker}</td>
              <td style={tdStyle}>{h.name ?? "—"}</td>
              <td style={{ ...tdStyle, color: theme.color.muted }}>{h.sector ?? "—"}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                <div style={weightCellStyle}>
                  <span style={barTrackStyle}>
                    <span style={{ ...barFillStyle, width: `${(h.weight / maxWeight) * 100}%` }} />
                  </span>
                  <span style={{ fontFamily: theme.font.mono, fontVariantNumeric: "tabular-nums", minWidth: 58, textAlign: "right" }}>
                    {pct(h.weight)}
                  </span>
                </div>
              </td>
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: theme.font.mono, fontVariantNumeric: "tabular-nums", color: theme.color.muted }}>
                {money(h.value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortHeader({
  label,
  active,
  asc,
  onClick,
  align = "left",
}: {
  label: ReactNode;
  active: boolean;
  asc: boolean;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <th
      onClick={onClick}
      style={{ ...thStyle, textAlign: align, cursor: "pointer", color: active ? theme.color.ink : theme.color.faint, userSelect: "none" }}
    >
      {label}
      <span style={{ opacity: active ? 1 : 0, fontSize: 9, marginLeft: 4 }}>{asc ? "▲" : "▼"}</span>
    </th>
  );
}

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontFamily: theme.font.sans,
  fontSize: 13,
};
const thStyle: CSSProperties = {
  padding: "8px 12px",
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: theme.color.faint,
  borderBottom: `1px solid ${theme.color.border}`,
  whiteSpace: "nowrap",
};
const tdStyle: CSSProperties = {
  padding: "9px 12px",
  borderBottom: `1px solid ${theme.color.grid}`,
  color: theme.color.ink,
  whiteSpace: "nowrap",
};
const weightCellStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  justifyContent: "flex-end",
};
const barTrackStyle: CSSProperties = {
  flex: 1,
  maxWidth: 120,
  height: 6,
  borderRadius: 3,
  background: theme.color.grid,
  overflow: "hidden",
};
const barFillStyle: CSSProperties = {
  display: "block",
  height: "100%",
  background: theme.color.accent,
  borderRadius: 3,
};
const emptyStyle: CSSProperties = {
  padding: 24,
  textAlign: "center",
  color: theme.color.muted,
  fontSize: 14,
};
