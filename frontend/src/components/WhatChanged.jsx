import VerdictBadge from "./VerdictBadge.jsx";

function daysAgoLabel(isoDate) {
  const days = Math.round((Date.now() - new Date(isoDate).getTime()) / 86400000);
  if (days <= 0) return "earlier today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function PriceChange({ previous, current }) {
  if (previous == null || current == null) return null;
  const pct = ((current - previous) / previous) * 100;
  const up = pct >= 0;
  const color = up ? "var(--success)" : "var(--danger)";
  return (
    <div>
      <div style={{ fontSize: "0.7rem", color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Price
      </div>
      <div style={{ fontSize: "0.95rem", marginTop: 2 }}>
        {previous.toLocaleString()} → {current.toLocaleString()}{" "}
        <span style={{ color, fontWeight: 600 }}>
          ({up ? "+" : ""}
          {pct.toFixed(1)}%)
        </span>
      </div>
    </div>
  );
}

function VerdictChange({ previous, current }) {
  if (!previous?.verdict || !current?.verdict) return null;
  const changed = previous.verdict !== current.verdict;
  return (
    <div>
      <div style={{ fontSize: "0.7rem", color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {changed ? "Verdict flipped" : "Verdict unchanged"}
      </div>
      <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 8 }}>
        <VerdictBadge verdict={previous.verdict} conviction={previous.conviction} size="sm" />
        <span style={{ color: "var(--text-faint)" }}>→</span>
        <VerdictBadge verdict={current.verdict} conviction={current.conviction} />
      </div>
    </div>
  );
}

export default function WhatChanged({ previous, current }) {
  if (!previous || !current || current.status !== "complete") return null;

  const prevPrice = previous.market_data?.price;
  const curPrice = current.market_data?.price;
  const verdictChanged = previous.verdict && current.verdict && previous.verdict !== current.verdict;

  if (prevPrice == null && !previous.verdict) return null;

  return (
    <div
      className="card fade-in"
      style={{
        marginBottom: 28,
        borderColor: verdictChanged ? "var(--gold)" : undefined,
      }}
    >
      <div
        style={{
          fontSize: "0.75rem",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color: "var(--text-faint)",
          marginBottom: 14,
        }}
      >
        Since you last saved this — {daysAgoLabel(previous.created_at)}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 28 }}>
        <PriceChange previous={prevPrice} current={curPrice} />
        <VerdictChange previous={previous} current={current} />
      </div>
    </div>
  );
}
