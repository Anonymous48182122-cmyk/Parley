import { useState } from "react";
import { compactMoney } from "../currency.js";

// The balance sheet, read for the kind of company it belongs to, at three depths. The server decides what each level
// holds: Basic is the few measures that carry about 60% of what matters for this kind of company, Advanced goes to
// about 75% and adds trends and what the company owns and owes, and Pro is everything the data allows, with the
// formulas, the year by year table and what the free data cannot show.

const LEVELS = [
  { id: "basic", label: "Basic", blurb: "The essentials" },
  { id: "advanced", label: "Advanced", blurb: "With trends and structure" },
  { id: "pro", label: "Pro", blurb: "The full reading" },
];
const RANK = { basic: 0, advanced: 1, pro: 2 };
const STATUS = {
  good: { label: "Strong", color: "var(--success)" },
  watch: { label: "Watch", color: "var(--gold)" },
  bad: { label: "Weak", color: "var(--danger)" },
  unknown: { label: "Context", color: "var(--text-faint)" },
};
const TONE = {
  strong: { color: "var(--success)", tint: "rgba(31, 201, 141, 0.08)" },
  mixed: { color: "var(--gold)", tint: "rgba(201, 160, 78, 0.08)" },
  weak: { color: "var(--danger)", tint: "rgba(240, 87, 106, 0.08)" },
  unknown: { color: "var(--text-dim)", tint: "rgba(255, 255, 255, 0.04)" },
};
const SEGMENT_COLORS = ["#c9a04e", "#38bdf8", "#8b7cf6", "#1fc98d", "#f5a623", "#ef5da8", "#6b7280"];

function amount(value, unit) {
  if (value == null) return "n/a";
  if (String(unit || "").includes("Cr")) return `₹${Math.round(value).toLocaleString("en-IN")} Cr`;
  return compactMoney(value, String(unit || "").slice(0, 3)) ?? "n/a";
}

function readStoredLevel() {
  try {
    const v = localStorage.getItem("parley.bsLevel");
    return v && RANK[v] !== undefined ? v : "basic";
  } catch {
    return "basic";
  }
}

function Trend({ points }) {
  if (!points || points.length < 2) return null;
  const values = points.map((p) => p.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const w = 84;
  const h = 26;
  const coords = values.map((v, i) => [(i / (values.length - 1)) * w, h - 3 - ((v - lo) / span) * (h - 6)]);
  return (
    <svg className="bs-trend" viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="img" aria-label={`Trend over ${points.length} years`}>
      <polyline points={coords.map((c) => c.join(",")).join(" ")} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <circle cx={coords[coords.length - 1][0]} cy={coords[coords.length - 1][1]} r="2.6" fill="currentColor" />
    </svg>
  );
}

function MetricRow({ m, level }) {
  const s = STATUS[m.status] || STATUS.unknown;
  return (
    <div className="bs-metric">
      <div className="bs-metric-head">
        <span className="bs-dot" style={{ background: s.color }} aria-hidden="true" />
        <span className="bs-metric-label">{m.label}</span>
        <span className="bs-chip" style={{ color: s.color, borderColor: s.color }}>{s.label}</span>
      </div>
      <div className="bs-metric-main">
        <div className="bs-metric-value">{m.display}</div>
        {RANK[level] >= 1 && m.trend && <span style={{ color: s.color }}><Trend points={m.trend} /></span>}
      </div>
      <div className="bs-metric-explain">{m.explain}</div>
      {level === "pro" && m.formula && <div className="bs-formula">How it is worked out: {m.formula}</div>}
    </div>
  );
}

function Bar({ title, items, unit }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="bs-bar-block">
      <div className="bs-bar-title">{title}</div>
      <div className="bs-bar" role="img" aria-label={title}>
        {items.map((x, i) => (
          <span key={x.label} style={{ flexGrow: Math.max(x.share, 0.5), background: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }} />
        ))}
      </div>
      <div className="bs-legend">
        {items.map((x, i) => (
          <span key={x.label}>
            <i style={{ background: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }} />
            {x.label} <b>{x.share.toFixed(0)}%</b> <em>{amount(x.value, unit)}</em>
          </span>
        ))}
      </div>
    </div>
  );
}

function YearTable({ years, unit }) {
  if (!years || !years.rows?.length) return null;
  return (
    <div className="bs-table-wrap">
      <table className="bs-table">
        <thead>
          <tr>
            <th />
            {years.periods.map((p) => (
              <th key={p}>{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.rows.map((r) => (
            <tr key={r.label}>
              <th>{r.label}</th>
              {r.values.map((v, i) => (
                <td key={i}>{amount(v, unit)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BalanceSheetCard({ reading }) {
  const [level, setLevel] = useState(readStoredLevel);
  if (!reading || !reading.metrics?.length) return null;

  function choose(id) {
    setLevel(id);
    try {
      localStorage.setItem("parley.bsLevel", id);
    } catch {
      // remembering the level is a nicety
    }
  }

  const tone = TONE[reading.verdict?.tone] || TONE.unknown;
  const shown = reading.metrics.filter((m) => RANK[m.level] <= RANK[level]);
  const cov = reading.coverage || {};
  const unit = reading.unit;

  return (
    <section className="bs card fade-in" aria-label="Balance sheet reading">
      <div className="lab-kicker">The balance sheet</div>
      <div className="lab-title">Is it financially sound? Read for a {reading.label}</div>

      <div className="bs-tabs" role="tablist" aria-label="How deep to read">
        {LEVELS.map((l) => (
          <button
            key={l.id}
            type="button"
            role="tab"
            aria-selected={level === l.id}
            className={`bs-tab${level === l.id ? " bs-tab--on" : ""}`}
            onClick={() => choose(l.id)}
          >
            <b>{l.label}</b>
            <span>{l.id === "pro" ? "Everything" : `About ${cov[l.id] ?? "?"}% of what matters`}</span>
          </button>
        ))}
      </div>

      <div className="bs-verdict" style={{ borderColor: tone.color, background: tone.tint }}>
        <span style={{ color: tone.color }}>{reading.verdict?.text}</span>
      </div>

      <div className="bs-metrics">
        {shown.map((m) => (
          <MetricRow key={m.id} m={m} level={level} />
        ))}
      </div>

      {RANK[level] >= 1 && (
        <>
          <Bar title="What it owns" items={reading.composition?.assets} unit={unit} />
          <Bar title="How it is funded" items={reading.composition?.funding} unit={unit} />
          <div className="bs-note">
            <b>How to read this kind of company</b>
            {reading.how_to_read}
          </div>
        </>
      )}

      {level === "pro" && (
        <>
          {reading.flags && (reading.flags.red.length > 0 || reading.flags.green.length > 0) && (
            <div className="bs-flags">
              {reading.flags.red.length > 0 && (
                <div>
                  <b style={{ color: "var(--danger)" }}>Red flags</b>
                  <span>{reading.flags.red.join(", ")}</span>
                </div>
              )}
              {reading.flags.green.length > 0 && (
                <div>
                  <b style={{ color: "var(--success)" }}>Strengths</b>
                  <span>{reading.flags.green.join(", ")}</span>
                </div>
              )}
            </div>
          )}

          <div className="bs-subhead">Year by year</div>
          <YearTable years={reading.years} unit={unit} />

          {reading.detail?.length > 0 && (
            <>
              <div className="bs-subhead">Balance sheet lines ({reading.period})</div>
              <div className="bs-lines">
                {reading.detail.map((d) => (
                  <div key={d.label}>
                    <span>{d.label}</span>
                    <b>{amount(d.value, unit)}</b>
                    <em>{d.share != null ? `${d.share.toFixed(0)}% of assets` : ""}</em>
                  </div>
                ))}
              </div>
            </>
          )}

          {reading.missing?.length > 0 && (
            <>
              <div className="bs-subhead">Not in our data</div>
              <div className="bs-missing">
                {reading.missing.map((x) => (
                  <div key={x.label}>
                    <b>{x.label}</b>
                    <span>{x.why}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      <div className="bs-foot">The ranges are rules of thumb for this kind of company, worked out from the figures. Not advice.</div>
    </section>
  );
}
