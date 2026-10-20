import { useId, useRef, useState } from "react";

// A small interactive price chart: a filled line over the recent closes, green when the
// stretch ended higher than it began and red when lower. Move across it to read the price
// at any point and how it compares with today.
export default function Sparkline({ values, symbol = "", height = 96 }) {
  const gradId = useId().replace(/:/g, "");
  const wrapRef = useRef(null);
  const [hover, setHover] = useState(null);

  if (!values || values.length < 5) return null;

  const W = 300;
  const H = 100;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 6;
  const x = (i) => (i / (values.length - 1)) * W;
  const y = (v) => pad + (1 - (v - min) / span) * (H - pad * 2);

  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  const up = values[values.length - 1] >= values[0];
  const color = up ? "var(--success)" : "var(--danger)";
  const last = values[values.length - 1];

  function onMove(e) {
    const rect = wrapRef.current.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    setHover(Math.round(frac * (values.length - 1)));
  }

  const shown = hover ?? values.length - 1;
  const price = values[shown];
  const vsNow = ((price - last) / last) * 100;

  return (
    <div className="sparkline" style={{ height }}>
      <div
        ref={wrapRef}
        className="sparkline-plot"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
        role="img"
        aria-label={`Price chart, ${up ? "up" : "down"} over the last ${values.length} trading days`}
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height="100%">
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.32" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill={`url(#${gradId})`} />
          <path d={line} fill="none" stroke={color} strokeWidth="1.8" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        </svg>
        <span
          className="sparkline-dot"
          style={{ left: `${(shown / (values.length - 1)) * 100}%`, top: `${(y(price) / H) * 100}%`, background: color }}
        />
        {hover !== null && (
          <span className="sparkline-cursor" style={{ left: `${(hover / (values.length - 1)) * 100}%` }} />
        )}
      </div>
      <div className="sparkline-readout">
        {hover !== null ? (
          <>
            <strong>
              {symbol}
              {price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </strong>
            <span style={{ color: vsNow >= 0 ? "var(--success)" : "var(--danger)" }}>
              {vsNow >= 0 ? "+" : ""}
              {vsNow.toFixed(1)}% vs now
            </span>
          </>
        ) : (
          <span>Last {values.length} trading days</span>
        )}
      </div>
    </div>
  );
}
