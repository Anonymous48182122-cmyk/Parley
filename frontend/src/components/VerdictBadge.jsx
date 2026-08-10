const VERDICT_COLORS = {
  BUY: "var(--success)",
  HOLD: "var(--text-dim)",
  SELL: "var(--danger)",
};

export default function VerdictBadge({ verdict, conviction, size = "md" }) {
  if (!verdict) return null;
  const color = VERDICT_COLORS[verdict] || "var(--text-dim)";
  const fontSize = size === "sm" ? "0.7rem" : "0.8rem";
  const padding = size === "sm" ? "3px 8px" : "5px 12px";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        border: `1px solid ${color}`,
        color,
        borderRadius: "var(--radius-sm)",
        padding,
        fontSize,
        fontWeight: 600,
        letterSpacing: "0.03em",
        whiteSpace: "nowrap",
      }}
    >
      {verdict}
      {conviction != null && (
        <span style={{ opacity: 0.75, fontWeight: 500 }}>{conviction}/10</span>
      )}
    </span>
  );
}
