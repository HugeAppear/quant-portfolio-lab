import type { CSSProperties } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { theme } from "./theme";
import DashboardPage from "./pages/DashboardPage";
import RunsPage from "./pages/RunsPage";
import ShortlistPage from "./pages/ShortlistPage";
import DataHealthPage from "./pages/DataHealthPage";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/runs", label: "Runs", end: false },
  { to: "/shortlist", label: "Shortlist", end: false },
  { to: "/data-health", label: "Data health", end: false },
];

export default function App() {
  return (
    <div style={shellStyle}>
      <aside style={sidebarStyle}>
        <div style={brandStyle}>
          <span style={brandMarkStyle}>Q</span>
          <span>
            <span style={brandNameStyle}>quant-portfolio-lab</span>
            <span style={brandSubStyle}>research console</span>
          </span>
        </div>

        <nav style={navStyle}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `qpl-nav${isActive ? " active" : ""}`}
              style={navLinkBaseStyle}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={sidebarFootStyle}>Backtests are not investment advice.</div>
      </aside>

      <main style={mainStyle}>
        <div style={contentStyle}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/shortlist" element={<ShortlistPage />} />
            <Route path="/data-health" element={<DataHealthPage />} />
            <Route path="*" element={<DashboardPage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

const shellStyle: CSSProperties = {
  display: "flex",
  minHeight: "100vh",
  background: theme.color.bg,
};
const sidebarStyle: CSSProperties = {
  width: 232,
  flexShrink: 0,
  background: theme.color.surface,
  borderRight: `1px solid ${theme.color.border}`,
  display: "flex",
  flexDirection: "column",
  padding: "20px 14px",
  position: "sticky",
  top: 0,
  height: "100vh",
};
const brandStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "0 8px 18px",
};
const brandMarkStyle: CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: 8,
  background: theme.color.accent,
  color: "#fff",
  display: "grid",
  placeItems: "center",
  fontFamily: theme.font.mono,
  fontWeight: 700,
  fontSize: 16,
  flexShrink: 0,
};
const brandNameStyle: CSSProperties = {
  display: "block",
  fontFamily: theme.font.mono,
  fontSize: 13,
  fontWeight: 600,
  color: theme.color.ink,
  lineHeight: 1.2,
};
const brandSubStyle: CSSProperties = {
  display: "block",
  fontSize: 11,
  color: theme.color.faint,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
};
const navStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 2, marginTop: 4 };
const navLinkBaseStyle: CSSProperties = {
  display: "block",
  padding: "9px 12px",
  borderRadius: theme.radius.sm,
  fontFamily: theme.font.sans,
  fontSize: 14,
  fontWeight: 500,
  color: theme.color.muted,
  textDecoration: "none",
};
const sidebarFootStyle: CSSProperties = {
  marginTop: "auto",
  padding: "0 8px",
  fontSize: 11,
  color: theme.color.faint,
  lineHeight: 1.5,
};
const mainStyle: CSSProperties = { flex: 1, minWidth: 0 };
const contentStyle: CSSProperties = {
  maxWidth: 1180,
  margin: "0 auto",
  padding: "28px 28px 56px",
};
