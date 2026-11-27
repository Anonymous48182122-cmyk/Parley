import { useEffect, useMemo, useRef, useState } from "react";
import { currencySymbol } from "../currency.js";
import { shortName } from "../agentMeta.js";

// Parley's own chart: the share price with the committee's price tags drawn on it. A green line is the price at
// which a member would buy, a red one where a member would sell or trim, each named. At a glance: how far is the
// price from where anyone would act. No other research app can draw this, because no other has a committee.

const RANGES = [
  { id: "1M", days: 22, label: "1M" },
  { id: "3M", days: 66, label: "3M" },
  { id: "6M", days: 130, label: "6M" },
  { id: "all", days: Infinity, label: "Max" },
];
const H = 300;
const PAD = { top: 14, bottom: 14, left: 4, right: 132 };
const FAR = 0.35; // a price tag further than this from today is listed under the chart instead of squashing it

function useWidth() {
  const ref = useRef(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const set = () => setW(Math.max(260, Math.round(el.getBoundingClientRect().width)));
    set();
    if (!("ResizeObserver" in window)) return undefined;
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export default function CommitteeChart({ closes, levels, price, currency }) {
  const all = useMemo(() => (closes || []).filter((v) => Number.isFinite(v)), [closes]);
  const [range, setRange] = useState("6M");
  const [hover, setHover] = useState(null);
  const [ref, width] = useWidth();

  if (all.length < 10) return null;
  const spec = RANGES.find((r) => r.id === range) || RANGES[2];
  const data = all.slice(-Math.min(spec.days, all.length));
  const today = price ?? data[data.length - 1];
  const narrow = width < 520;
  const right = narrow ? 70 : PAD.right;
  const sym = currencySymbol(currency || "USD");
  const money = (n) => `${sym}${Number(n).toLocaleString(undefined, { maximumFractionDigits: n >= 100 ? 0 : 2 })}`;

  const near = (levels || []).filter((l) => Math.abs(l.price / today - 1) <= FAR);
  const far = (levels || []).filter((l) => !near.includes(l));
  const lo0 = Math.min(...data, ...near.map((l) => l.price), today);
  const hi0 = Math.max(...data, ...near.map((l) => l.price), today);
  const pad = (hi0 - lo0 || hi0 * 0.05) * 0.07;
  const lo = lo0 - pad;
  const hi = hi0 + pad;

  const plot = width - PAD.left - right;
  const x = (i) => PAD.left + (i / (data.length - 1)) * plot;
  const y = (v) => PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);
  const line = data.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const change = ((data[data.length - 1] - data[0]) / data[0]) * 100;

  // name tags down the right edge, nudged apart so they never sit on top of each other
  const tags = [...near.map((l) => ({ ...l, y: y(l.price) })), { now: true, price: today, y: y(today) }].sort((a, b) => a.y - b.y);
  const GAP = narrow ? 26 : 30;
  tags.forEach((t, i) => (t.ty = i ? Math.max(t.y, tags[i - 1].ty + GAP) : Math.max(t.y, 12)));
  for (let i = tags.length - 1; i >= 0; i--) {
    const max = i === tags.length - 1 ? H - 14 : tags[i + 1].ty - GAP;
    tags[i].ty = Math.min(tags[i].ty, max);
  }

  const who = (l) => {
    const names = l.who.map((n) => shortName(n));
    return names.length > 2 ? `${names[0]} +${names.length - 1}` : names.join(", ");
  };

  function move(e) {
    const box = e.currentTarget.getBoundingClientRect();
    const px = (e.touches ? e.touches[0].clientX : e.clientX) - box.left;
    const i = Math.round(((px - PAD.left) / plot) * (data.length - 1));
    setHover(i >= 0 && i < data.length ? i : null);
  }

  return (
    <figure className="cchart" ref={ref}>
      <div className="cchart-head">
        <div>
          <div className="cchart-title">Price, and where the committee would act</div>
          <div className="cchart-sub">
            {hover == null ? (
              <span className={change >= 0 ? "up" : "down"}>
                {change >= 0 ? "+" : ""}
                {change.toFixed(1)}% over {spec.id === "all" ? `${data.length} trading days` : spec.label}
              </span>
            ) : (
              <span>
                <b>{money(data[hover])}</b> {data.length - 1 - hover === 0 ? "latest close" : `${data.length - 1 - hover} trading days ago`}
              </span>
            )}
          </div>
        </div>
        <div className="seg" role="tablist" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r.id} type="button" role="tab" aria-selected={range === r.id} className={range === r.id ? "on" : ""} onClick={() => setRange(r.id)}>
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <svg width={width} height={H} role="img" aria-label="Share price with the prices at which committee members would buy or sell" onMouseMove={move} onMouseLeave={() => setHover(null)} onTouchStart={move} onTouchMove={move} onTouchEnd={() => setHover(null)}>
        {[0.25, 0.5, 0.75].map((f) => {
          const v = lo + (hi - lo) * f;
          return (
            <g key={f}>
              <line x1={PAD.left} x2={PAD.left + plot} y1={y(v)} y2={y(v)} className="cchart-grid" />
              <text x={PAD.left} y={y(v) - 4} className="cchart-axis">{money(v)}</text>
            </g>
          );
        })}
        {near.map((l) => (
          <line key={`${l.side}${l.price}`} x1={PAD.left} x2={PAD.left + plot} y1={y(l.price)} y2={y(l.price)} className={`cchart-level cchart-level--${l.side}`} />
        ))}
        <path d={`${line} L${x(data.length - 1)} ${H - PAD.bottom} L${x(0)} ${H - PAD.bottom} Z`} className="cchart-area" />
        <path d={line} className="cchart-line" />
        <circle cx={x(data.length - 1)} cy={y(data[data.length - 1])} r="4" className="cchart-dot" />
        {tags.map((t) => (
          <g key={t.now ? "now" : `${t.side}${t.price}`} className={`cchart-tag cchart-tag--${t.now ? "now" : t.side}`}>
            <path d={`M${PAD.left + plot} ${t.y} L${PAD.left + plot + 8} ${t.ty}`} />
            <text x={PAD.left + plot + 12} y={t.ty - 2}>{money(t.price)}</text>
            <text x={PAD.left + plot + 12} y={t.ty + 11} className="cchart-tag-who">
              {t.now ? "Today" : narrow ? (t.side === "below" ? "Buy" : "Sell") : who(t)}
            </text>
          </g>
        ))}
        {hover != null && (
          <g className="cchart-cross">
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} />
            <circle cx={x(hover)} cy={y(data[hover])} r="3.5" />
          </g>
        )}
      </svg>

      <figcaption className="cchart-key">
        <span className="k-buy">Would buy at or below</span>
        <span className="k-sell">Would sell at or above</span>
        {far.map((l) => (
          <span key={`${l.side}${l.price}`} className="k-far">
            Off the chart: {who(l)} {l.side === "below" ? "buys" : "sells"} at {money(l.price)}
          </span>
        ))}
        {(!levels || levels.length === 0) && <span className="k-far">No member has named a price yet.</span>}
      </figcaption>
    </figure>
  );
}
