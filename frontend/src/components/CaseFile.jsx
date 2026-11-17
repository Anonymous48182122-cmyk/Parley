import "../casefile.css";
import { useEffect, useMemo, useState } from "react";
import { buildCaseFile } from "../caseFile.js";
import { currencySymbol } from "../currency.js";

// The company's case file: a button beside the name that opens a one page file on the company. It is not an
// encyclopaedia entry. It holds only what helps a decision: what the company is, what its numbers really say,
// the few things most people miss, who runs it and what the market's mood is. All of it comes from figures
// Parley already has, so it opens instantly and every line can be traced to a number.

const VERDICT_COLORS = { BUY: "var(--success)", HOLD: "var(--gold)", SELL: "var(--danger)" };

// A chart icon: a square, its two diagonals and the diamond joining the midpoints.
function ChartIcon({ size = 20 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true">
      <rect x="2.75" y="2.75" width="18.5" height="18.5" rx="1.5" />
      <path d="M2.75 2.75 21.25 21.25M21.25 2.75 2.75 21.25" />
      <path d="M12 2.75 21.25 12 12 21.25 2.75 12Z" />
    </svg>
  );
}

function Section({ title, children }) {
  return (
    <section className="kd-sec">
      <h3 className="kd-sec-title">{title}</h3>
      {children}
    </section>
  );
}

function FlowBars({ flow }) {
  const rows = [
    ["Sales", 100, "var(--text-faint)"],
    flow.gross != null && ["Left after making it", flow.gross, "#38bdf8"],
    flow.operating != null && ["Left after running it", flow.operating, "var(--gold)"],
    ["Kept as profit", flow.net, "var(--success)"],
  ].filter(Boolean);
  return (
    <div className="kd-flow" role="img" aria-label="Where each 100 of sales goes">
      {rows.map(([label, v, color]) => (
        <div key={label} className="kd-flow-row">
          <span>{label}</span>
          <i><b style={{ width: `${Math.max(2, Math.min(100, v))}%`, background: color }} /></i>
          <em>{Math.round(v)}</em>
        </div>
      ))}
    </div>
  );
}

function Body({ k, onFull }) {
  const sym = currencySymbol(k.mood?.currency || "USD");
  const fmt = (n) => (n == null ? "" : `${sym}${Number(n).toLocaleString(undefined, { maximumFractionDigits: n >= 100 ? 0 : 2 })}`);
  return (
    <>
      <div className="kd-ident">
        {k.identity.map((i) => (
          <div key={i.label}>
            <span>{i.label}</span>
            <b>{i.value}</b>
            {i.note && <em>{i.note}</em>}
          </div>
        ))}
      </div>

      {k.born && (
        <Section title="What it is">
          <p className="kd-born">{k.born}</p>
        </Section>
      )}

      {k.flow && (
        <Section title="Where each 100 of sales goes">
          <FlowBars flow={k.flow} />
        </Section>
      )}

      {k.vitals.length > 0 && (
        <Section title="Vital signs">
          <div className="kd-vitals">
            {k.vitals.map((v) => (
              <div key={v.label} className={`kd-vital kd-vital--${v.tone}`}>
                <span className="kd-vital-label">{v.label}</span>
                <b>{v.value}</b>
                <span className="kd-vital-line">{v.line}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {k.insights.length > 0 && (
        <Section title="What most people miss">
          <div className="kd-miss">
            {k.insights.map((x) => (
              <div key={x.title} className={`kd-miss-item kd-miss-item--${x.tone}`}>
                <b>{x.title}</b>
                <p>{x.text}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {k.people && (
        <Section title="Who runs it, and their skin in the game">
          {k.people.leaders.length > 0 && (
            <div className="kd-people">
              {k.people.leaders.map((l) => (
                <span key={l.name} className="kd-person">
                  <b>{l.name}</b>
                  {l.tag && <em>{l.tag}</em>}
                </span>
              ))}
            </div>
          )}
          {k.people.lines.map((t) => (
            <p key={t} className="kd-line">{t}</p>
          ))}
        </Section>
      )}

      {k.mood && (
        <Section title="The market's mood">
          <div className="kd-range">
            <span>{fmt(k.mood.low)}</span>
            <div className="kd-range-track">
              <i style={{ left: `${k.mood.position}%` }} />
            </div>
            <span>{fmt(k.mood.high)}</span>
          </div>
          <div className="kd-range-cap">Where the price sits in its range of the last year</div>
          <div className="kd-tags">
            {k.mood.tags.map((t) => (
              <span key={t.text} className={`kd-tag kd-tag--${t.tone}`}>{t.text}</span>
            ))}
          </div>
        </Section>
      )}

      {k.verdict && (
        <Section title="What the committee decided">
          <div className="kd-verdict" style={{ "--verdict": VERDICT_COLORS[k.verdict.call] || "var(--text-dim)" }}>
            <b>{k.verdict.call || "No call"}{k.verdict.conviction != null ? ` · ${k.verdict.conviction}/10` : ""}</b>
            <p>{k.verdict.headline}</p>
            <button type="button" className="button-secondary" onClick={onFull}>Open the full analysis</button>
          </div>
        </Section>
      )}

      <div className="kd-foot">Worked out from the company's reported figures. Not advice.</div>
    </>
  );
}

export default function CaseFile({ model, onFull }) {
  const [open, setOpen] = useState(false);
  const k = useMemo(() => (open ? buildCaseFile(model) : null), [open, model]);

  useEffect(() => {
    if (!open) return undefined;
    function esc(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", esc);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", esc);
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!model.marketData) return null;

  return (
    <>
      <button type="button" className="kd-btn" onClick={() => setOpen(true)} aria-haspopup="dialog" title="The company's case file: what it is, what its numbers say, what most people miss">
        <ChartIcon />
        <span>Case file</span>
      </button>

      {open && k && (
        <div className="kd-overlay" onClick={() => setOpen(false)}>
          <div className="kd-sheet" role="dialog" aria-modal="true" aria-label={`Case file on ${k.name}`} onClick={(e) => e.stopPropagation()}>
            <header className="kd-head">
              <span className="kd-head-icon"><ChartIcon size={26} /></span>
              <div>
                <div className="lab-kicker">Company case file</div>
                <div className="kd-title">{k.name}</div>
              </div>
              <button type="button" className="kd-close" onClick={() => setOpen(false)} aria-label="Close">×</button>
            </header>
            <div className="kd-scroll">
              <Body k={k} onFull={() => { setOpen(false); onFull?.(); }} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
