import "../floor.css";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { SIDES, floorMembers, groupAt, money, portraitOf, priceRange, roomCall, sideAt, symbolOf } from "../floor.js";
import FloorStage from "./FloorStage.jsx";
import Jargon from "./Jargon.jsx";

// The Floor: the committee as a room you can move. Members stand under For, Waiting or Against. Drag the price and
// they cross sides at the prices they named, and the call changes with them. While a session is live they walk in
// as they finish reading, and whoever is speaking is lit.

const WORD = { BUY: "Buy", HOLD: "Hold", SELL: "Sell" };
const TONE = { BUY: "for", HOLD: "wait", SELL: "against" };
const NUMBERS = ["nobody", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];
const count = (n) => NUMBERS[n] ?? String(n);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function useSize(ref) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const read = () => setSize({ w: Math.round(el.clientWidth), h: Math.round(el.clientHeight) });
    read();
    if (!("ResizeObserver" in window)) return undefined;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

// The biggest portraits that fit `n` of them in a w by h space.
function bestGrid(n, w, h) {
  let best = { area: 0, cols: 1, tw: 0, th: 0 };
  for (let cols = 1; cols <= n; cols++) {
    const rows = Math.ceil(n / cols);
    const tw = (w - (cols - 1) * 8) / cols;
    const th = (h - (rows - 1) * 8) / rows;
    const width = Math.min(tw, th * 1.12);
    const height = Math.min(th, width * 1.3);
    if (width * height > best.area) best = { area: width * height, cols, tw: width, th: height };
  }
  return best;
}

// Where every zone and every member goes. Wide screens: the camps side by side, each given room in proportion to
// how many it holds. Phones: the camps stacked, four faces across.
function arrange(zones, groups, W, H, phone) {
  const seats = {};
  const boxes = {};
  if (!W) return { seats, boxes, height: 0 };
  if (phone) {
    const cols = W > 520 ? 5 : 4;
    const tw = (W - (cols - 1) * 6) / cols;
    const th = tw * 1.22;
    let top = 0;
    for (const z of zones) {
      const list = groups[z.id];
      const rows = Math.ceil(list.length / cols);
      const height = 58 + (rows ? rows * (th + 6) + 6 : 40);
      boxes[z.id] = { left: 0, width: W, top, height };
      list.forEach((m, i) => (seats[m.key] = { x: (i % cols) * (tw + 6), y: top + 58 + Math.floor(i / cols) * (th + 6), w: tw, h: th }));
      top += height;
    }
    return { seats, boxes, height: top };
  }
  const HEAD = 60;
  const PAD = 14;
  const weights = zones.map((z) => Math.max(groups[z.id].length, 1.2));
  const total = weights.reduce((a, b) => a + b, 0);
  let left = 0;
  zones.forEach((z, i) => {
    const width = (W * weights[i]) / total;
    const list = groups[z.id];
    boxes[z.id] = { left, width, top: 0, height: H };
    if (list.length) {
      const g = bestGrid(list.length, width - 2 * PAD, H - HEAD - 12);
      const used = g.cols * g.tw + (g.cols - 1) * 8;
      const x0 = left + PAD + (width - 2 * PAD - used) / 2;
      list.forEach((m, j) => {
        const row = Math.floor(j / g.cols);
        const inRow = Math.min(g.cols, list.length - row * g.cols);
        const shift = ((g.cols - inRow) * (g.tw + 8)) / 2;
        seats[m.key] = { x: x0 + shift + (j % g.cols) * (g.tw + 8), y: HEAD + row * (g.th + 8), w: g.tw, h: g.th };
      });
    }
    left += width;
  });
  return { seats, boxes, height: H };
}

export function Face({ memberKey, className = "" }) {
  const src = portraitOf(memberKey);
  return src ? <img className={className} src={src} alt="" draggable="false" /> : <span className={`fl-symbol ${className}`} aria-hidden="true">{symbolOf(memberKey)}</span>;
}

// ---- the price, which the reader can drag ----------------------------------------------------------------
function PriceChart({ closes, members, price, today, range, currency, phone, onPrice, tone }) {
  const ref = useRef(null);
  const { w: W, h: H } = useSize(ref);
  const dragging = useRef(false);
  const [lo, hi] = range;
  const R = phone ? 86 : 108;
  const gap = phone ? 16 : 19;
  const y = (v) => 8 + (1 - (v - lo) / (hi - lo || 1)) * (H - 16);
  const data = (closes || []).slice(-130);
  const x = (i) => (i / Math.max(1, data.length - 1)) * (W - R - 26);
  const path = data.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");

  // a face at every price someone named, on a ruler beside the chart, pushed sideways where they would collide
  const marks = useMemo(() => {
    const list = members.flatMap((m) => [["buy", m.buy], ["sell", m.sell]].filter(([, p]) => p != null && p >= lo && p <= hi).map(([kind, p]) => ({ m, kind, p })));
    return list.sort((a, b) => b.p - a.p);
  }, [members, lo, hi]);
  const placed = [];
  const maxCols = Math.max(1, Math.floor((R - 16) / gap));
  const laid = marks.map((mk) => {
    const yy = y(mk.p);
    let col = 0;
    while (col < maxCols - 1 && placed.some((u) => u.col === col && Math.abs(u.y - yy) < 19)) col++;
    placed.push({ col, y: yy });
    return { ...mk, yy, cx: W - R + 16 + col * gap };
  });

  function at(e) {
    const top = ref.current.getBoundingClientRect().top;
    onPrice(lo + (1 - (e.clientY - top - 8) / (H - 16)) * (hi - lo));
  }
  function key(e) {
    const step = (today * (e.shiftKey ? 0.05 : 0.01)) || 1;
    if (e.key === "ArrowUp" || e.key === "ArrowRight") { e.preventDefault(); onPrice(price + step); }
    if (e.key === "ArrowDown" || e.key === "ArrowLeft") { e.preventDefault(); onPrice(price - step); }
    if (e.key === "Home" || e.key === "Escape") { e.preventDefault(); onPrice(today); }
  }
  const grid = [0.2, 0.5, 0.8].map((f) => lo + (hi - lo) * f);

  return (
    <div
      ref={ref}
      className="fl-chart"
      role="slider"
      tabIndex={0}
      aria-label="Try a different share price"
      aria-valuemin={Math.round(lo)}
      aria-valuemax={Math.round(hi)}
      aria-valuenow={Number(price.toFixed(2))}
      aria-valuetext={money(price, currency)}
      onKeyDown={key}
      onPointerDown={(e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); at(e); }}
      onPointerMove={(e) => dragging.current && at(e)}
      onPointerUp={() => (dragging.current = false)}
      onPointerCancel={() => (dragging.current = false)}
    >
      {W > 0 && (
        <svg width={W} height={H} aria-hidden="true">
          {grid.map((v) => (
            <g key={v}>
              <line x1="0" x2={W - R} y1={y(v)} y2={y(v)} className="fl-grid" />
              <text x="0" y={y(v) - 4} className="fl-axis">{money(Math.round(v), currency)}</text>
            </g>
          ))}
          {data.length > 1 && (
            <>
              <path d={path} className="fl-line" />
              <circle cx={x(data.length - 1)} cy={y(data[data.length - 1])} r="3.5" className="fl-dot" />
            </>
          )}
          {laid.map((mk) => {
            const hit = mk.kind === "buy" ? price <= mk.p : price >= mk.p;
            const id = `flc-${mk.m.key}-${mk.kind}`;
            const src = portraitOf(mk.m.key);
            return (
              <g key={id} className={`fl-mark fl-mark--${mk.kind}${hit ? " fl-mark--hit" : ""}`}>
                <title>{`${mk.m.name}: ${mk.kind === "buy" ? "buys at" : "sells at"} ${money(mk.p, currency)}`}</title>
                <line x1={W - R - 26} x2={mk.cx - 10} y1={mk.yy} y2={mk.yy} />
                <clipPath id={id}><circle cx={mk.cx} cy={mk.yy} r="9" /></clipPath>
                {src ? (
                  <image href={src} x={mk.cx - 9} y={mk.yy - 9} width="18" height="18" clipPath={`url(#${id})`} />
                ) : (
                  <>
                    <circle cx={mk.cx} cy={mk.yy} r="9" className="fl-mark-bg" />
                    <text x={mk.cx} y={mk.yy + 4} textAnchor="middle" className="fl-mark-sym">{symbolOf(mk.m.key)}</text>
                  </>
                )}
                <circle cx={mk.cx} cy={mk.yy} r="9.5" className="fl-ring" />
              </g>
            );
          })}
          <g className={`fl-handle fl-tone--${tone}`} style={{ transform: `translateY(${y(price)}px)` }}>
            <line x1="0" x2={W - R} />
            <rect x={W - R - 96} y="-13" width="92" height="26" rx="13" />
            <text x={W - R - 50} y="4.5" textAnchor="middle">{money(price, currency)}</text>
          </g>
        </svg>
      )}
    </div>
  );
}

export default function Floor({ model, brief, speaking }) {
  const members = useMemo(() => floorMembers(model), [model.stage1, model.debate, model.agents, model.scorecards, model.priceLevels, model.plainBrief, model.status, model.price]); // eslint-disable-line react-hooks/exhaustive-deps
  const today = Number(model.price) > 0 ? Number(model.price) : null;
  const closes = model.marketData?.technicals?.closes;
  const [tried, setTried] = useState(null);
  const [stage, setStage] = useState(null); // { index, auto }
  const [entered, setEntered] = useState(false);
  const floorRef = useRef(null);
  const { w: W, h: H } = useSize(floorRef);
  const [phone, setPhone] = useState(() => window.matchMedia?.("(max-width: 900px)").matches ?? false);

  useEffect(() => {
    const mq = window.matchMedia?.("(max-width: 900px)");
    const on = () => setPhone(mq.matches);
    mq?.addEventListener?.("change", on);
    return () => mq?.removeEventListener?.("change", on);
  }, []);
  // the opening: everyone starts in the middle of the room and walks to their side
  useEffect(() => {
    if (!W) return undefined;
    const t = setTimeout(() => setEntered(true), 120);
    return () => clearTimeout(t);
  }, [W]);
  useEffect(() => setTried(null), [model.ticker, today]);

  const price = tried ?? today;
  const trying = tried != null && tried !== today;
  const groups = groupAt(members, price, today);
  const hasMemo = model.hasMemo;
  const reading = groups.reading.length;
  const zones = reading ? [{ id: "reading", label: "Reading" }, ...SIDES] : SIDES;
  const layout = arrange(zones, groups, W, H, phone);
  const call = trying ? roomCall(groups) : hasMemo ? model.verdict || "HOLD" : null;
  const tone = call ? TONE[call] : "quiet";
  const range = today ? priceRange(members, closes, today) : null;
  const heard = members.length - reading;
  const withLimits = members.filter((m) => m.buy != null || m.sell != null).length;
  const currency = model.currency;

  function tryPrice(v) {
    if (!today || !range) return;
    let next = Math.max(range[0], Math.min(range[1], v));
    if (Math.abs(next / today - 1) < 0.008) return setTried(null); // today's price is easy to come back to
    const step = today >= 2000 ? 5 : today >= 500 ? 1 : today >= 50 ? 0.25 : 0.05;
    next = Math.round(next / step) * step;
    return setTried(Number(next.toFixed(2)));
  }

  let sentence;
  if (trying) {
    sentence = (
      <>
        At {money(price, currency)}, <b>{count(groups.for.length)} would own it</b> and {groups.against.length ? `${count(groups.against.length)} would stay away` : "nobody would stay away"}.
      </>
    );
  } else if (hasMemo) {
    sentence = <Jargon text={brief.headline} />;
  } else if (!heard) {
    sentence = "The committee is reading the filings, prices and ratios.";
  } else if (speaking) {
    sentence = "The debate is on. Watch who changes sides.";
  } else {
    sentence = `${cap(count(heard))} of ${members.length} have made up their minds.`;
  }

  const speakers = useMemo(() => {
    // for and against take turns, so the argument sounds like one
    const by = { for: [], against: [], wait: [] };
    members.filter((m) => m.line).forEach((m) => by[m.base]?.push(m));
    const out = [];
    while (by.for.length || by.against.length || by.wait.length) {
      for (const side of ["for", "against", "wait"]) if (by[side].length) out.push(by[side].shift());
    }
    return out;
  }, [members]);

  if (!members.length) return null;

  return (
    <section className={`fl fl-tone--${tone}`} aria-label="The committee floor">
      <div className="fl-ruling">
        <div className="fl-word" aria-live="polite">
          <span key={call || "wait"} className={call ? "" : "fl-word--wait"}>{call ? WORD[call] : "Sitting"}</span>
        </div>
        <div className="fl-say">
          <p>{sentence}</p>
          <div className="fl-sub">
            {trying ? (
              <>
                <span>A what if, from the prices members named.</span>
                <button type="button" onClick={() => setTried(null)}>Back to today</button>
              </>
            ) : hasMemo ? (
              <span>
                {model.conviction != null ? `The chairman is ${model.conviction} out of 10 sure of this call.` : "The chairman gave no score."}
                {model.cioFallback ? " This is an automatic summary." : ""}
              </span>
            ) : (
              <span>{model.status === "running" ? "Live now." : "The session ended without a ruling."}</span>
            )}
          </div>
        </div>
        {speakers.length > 0 && (
          <button type="button" className="fl-play" onClick={() => setStage({ index: 0, auto: true })}>
            <i aria-hidden="true" />
            Hear the argument
          </button>
        )}
      </div>

      <div className={`fl-floor${phone ? " fl-floor--stack" : ""}`} ref={floorRef} style={phone ? { height: layout.height } : undefined}>
        {zones.map((z) => {
          const b = layout.boxes[z.id];
          if (!b) return null;
          return (
            <div key={z.id} className={`fl-zone fl-zone--${z.id}`} style={phone ? { top: b.top, height: b.height } : { left: b.left, width: b.width }}>
              <h2>
                {z.label}
                <em>{groups[z.id].length}</em>
              </h2>
              {!groups[z.id].length && <p>{trying ? "Nobody, at this price." : "Nobody."}</p>}
            </div>
          );
        })}
        {members.map((m, i) => {
          const side = sideAt(m, price, today);
          const seat = entered ? layout.seats[m.key] : { x: W / 2 - 50, y: Math.max(60, (H || 300) / 2 - 60), w: 100, h: 120 };
          if (!seat) return null;
          const moved = trying && side !== m.base;
          const status = side === "reading" ? "reading" : speaking === m.key ? "has the floor" : moved ? "changed side" : m.buy != null ? `buys at ${money(m.buy, currency)}` : m.sell != null ? `sells at ${money(m.sell, currency)}` : m.changedInDebate ? "changed in debate" : "no price";
          return (
            <button
              key={m.key}
              type="button"
              className={`fl-seat fl-seat--${side}${moved ? " fl-seat--moved" : ""}${speaking === m.key ? " fl-seat--speaking" : ""}`}
              style={{ transform: `translate(${seat.x}px, ${seat.y}px)`, width: seat.w, height: seat.h, opacity: entered ? undefined : 0, transitionDelay: entered && !trying && model.status !== "running" ? `${i * 45}ms` : "0ms", "--size": `${Math.min(seat.w, seat.h)}px` }}
              disabled={!m.line}
              aria-label={`${m.name}, ${side === "wait" ? "waiting" : side}. ${status}`}
              onClick={() => setStage({ index: speakers.findIndex((s) => s.key === m.key), auto: false })}
            >
              <span className="fl-plate">
                <Face memberKey={m.key} />
              </span>
              <span className="fl-cap">
                <b>{m.short}</b>
                <span>{status}</span>
              </span>
            </button>
          );
        })}
      </div>

      {today && range && (
        <div className="fl-price">
          <div className="fl-ask">
            <div className="fl-label">{trying ? "If the price were" : "Today's price"}</div>
            <div className="fl-big">{money(price, currency)}</div>
            <div className="fl-delta">{trying ? `${Math.abs((price / today - 1) * 100).toFixed(1)}% ${price < today ? "below" : "above"} today` : withLimits ? "Drag to try another" : "No member has named a price yet"}</div>
            {withLimits > 0 && (
              <p>
                <b>Drag the price.</b> Members change sides at the prices they named. Arrow keys work too.
              </p>
            )}
          </div>
          <PriceChart closes={closes} members={members} price={price} today={today} range={range} currency={currency} phone={phone} onPrice={tryPrice} tone={tone} />
        </div>
      )}

      {stage && speakers.length > 0 && (
        <FloorStage speakers={speakers} start={Math.max(0, stage.index)} autoStart={stage.auto} price={price} today={today} currency={currency} onClose={() => setStage(null)} />
      )}
    </section>
  );
}
