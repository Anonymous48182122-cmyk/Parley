const COLORS = {
  BUY: "var(--success)",
  HOLD: "var(--gold)",
  SELL: "var(--danger)",
};

// A small ring filled to the conviction score, in the colour of the verdict. The static
// sibling of the big animated gauge on the CIO memo, for lists.
export default function ConvictionRing({ verdict, conviction, size = 52 }) {
  const color = COLORS[verdict] || "var(--text-faint)";
  const r = 20;
  const c = 2 * Math.PI * r;
  const frac = Math.min(1, Math.max(0, (conviction ?? 0) / 10));
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 50 50"
      role="img"
      aria-label={`${verdict || "No call"}, conviction ${conviction ?? "unknown"} out of 10`}
      style={{ flexShrink: 0 }}
    >
      <circle cx="25" cy="25" r={r} fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth="4" />
      <circle
        cx="25"
        cy="25"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={`${c * frac} ${c}`}
        transform="rotate(-90 25 25)"
      />
      <text x="25" y="30" textAnchor="middle" fontSize="15" fontWeight="600" fill="currentColor">
        {conviction ?? "–"}
      </text>
    </svg>
  );
}
