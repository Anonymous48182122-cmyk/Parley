import { useState } from "react";
import { AGENT_META, AGENT_ORDER } from "../agentMeta.js";
import BioAvatar from "./BioAvatar.jsx";

// The Business Lab: what the company really is, where each 100 of sales goes, how the committee rates
// the business itself (apart from the share price), and who runs it. Everything here is either
// computed from the figures (the money flow, the management numbers) or written by the committee
// from the same figures (the scorecards and the business card), so a missing piece simply hides.

const FLOW_STEPS = [
  { key: "gross", label: "Left after making the product", tone: "var(--gold)" },
  { key: "operating", label: "Left after running the business", tone: "var(--success)" },
  { key: "net", label: "Kept as profit", tone: "var(--success)" },
];

function scoreTone(score) {
  if (score >= 8) return "var(--success)";
  if (score >= 6) return "var(--gold)";
  if (score >= 4) return "#e0883e";
  return "var(--danger)";
}

function verdictWord(avg) {
  if (avg >= 8) return "An exceptional business";
  if (avg >= 6.5) return "A strong business";
  if (avg >= 5) return "A decent business";
  if (avg >= 3.5) return "A weak business";
  return "A troubled business";
}

function money(value, currency) {
  if (value == null) return "not known";
  if (currency === "INR") return `₹${(value / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr`;
  const abs = Math.abs(value);
  const sym = currency === "USD" || !currency ? "$" : "";
  if (abs >= 1e9) return `${sym}${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sym}${(value / 1e6).toFixed(1)}M`;
  return `${sym}${Math.round(value).toLocaleString("en-US")}`;
}

function MoneyFlow({ flow }) {
  if (!flow) return null;
  const rows = FLOW_STEPS.filter((s) => flow[s.key] != null);
  if (rows.length === 0) return null;
  const net = flow.net;
  return (
    <div className="lab-card">
      <div className="lab-kicker">Follow the money</div>
      <div className="lab-title">Out of every 100 a customer pays</div>
      <div className="lab-flow">
        <div className="lab-flow-row">
          <span className="lab-flow-label">What customers pay</span>
          <div className="lab-flow-track">
            <div className="lab-flow-fill" style={{ width: "100%", background: "var(--text-faint)" }} />
          </div>
          <span className="lab-flow-value">100</span>
        </div>
        {rows.map((s, i) => {
          const v = flow[s.key];
          return (
            <div className="lab-flow-row" key={s.key}>
              <span className="lab-flow-label">{s.label}</span>
              <div className="lab-flow-track">
                <div
                  className="lab-flow-fill"
                  style={{
                    width: `${Math.max(0, Math.min(100, v))}%`,
                    background: v < 0 ? "var(--danger)" : s.tone,
                    animationDelay: `${(i + 1) * 140}ms`,
                  }}
                />
              </div>
              <span className="lab-flow-value" style={{ color: v < 0 ? "var(--danger)" : undefined }}>
                {v.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
      {net != null && (
        <div className="lab-caption">
          {net < 0
            ? `Right now the business loses ${Math.abs(net).toFixed(1)} on every 100 it sells.`
            : `For every 100 in sales, ${net.toFixed(1)} ends up as profit. Figures are for ${flow.period}.`}
        </div>
      )}
    </div>
  );
}

function Scorecards({ scorecards, order }) {
  const entries = order.filter((k) => scorecards?.[k]).map((k) => ({ key: k, ...scorecards[k] }));
  const [picked, setPicked] = useState(null);
  if (entries.length === 0) return null;

  const avg = entries.reduce((s, e) => s + e.score, 0) / entries.length;
  const fan = entries.reduce((a, b) => (b.score > a.score ? b : a));
  const critic = entries.reduce((a, b) => (b.score < a.score ? b : a));
  const current = entries.find((e) => e.key === (picked || fan.key)) || fan;
  const tone = scoreTone(avg);

  const rows = [
    { label: "The Great", text: current.great, tone: "var(--success)" },
    { label: "The Bad", text: current.bad, tone: "#e0883e" },
    { label: "The Gruesome", text: current.gruesome, tone: "var(--danger)" },
  ];

  return (
    <div className="lab-card">
      <div className="lab-kicker">The committee rates the business</div>
      <div className="lab-title">Not the share price. The machine that makes the money.</div>

      <div className="lab-avg">
        <div className="lab-avg-number" style={{ color: tone }}>
          {avg.toFixed(1)}
          <small>/10</small>
        </div>
        <div>
          <div className="lab-avg-word" style={{ color: tone }}>{verdictWord(avg)}</div>
          <div className="lab-sub">
            Average of {entries.length} ratings, from {critic.score} to {fan.score}.
          </div>
        </div>
      </div>

      <div className="lab-agents" role="tablist" aria-label="Pick a committee member">
        {entries.map((e) => (
          <button
            key={e.key}
            type="button"
            role="tab"
            aria-selected={e.key === current.key}
            className={`lab-agent${e.key === current.key ? " lab-agent--on" : ""}`}
            onClick={() => setPicked(e.key)}
          >
            <span className="lab-agent-ring" style={{ borderColor: scoreTone(e.score) }}>
              <BioAvatar agentKey={e.key} size="sm" />
              <b style={{ background: scoreTone(e.score) }}>{e.score}</b>
            </span>
            <span className="lab-agent-name">{AGENT_META[e.key]?.name?.split(" ").slice(-1)[0] || e.key}</span>
            {e.key === fan.key && entries.length > 1 && <i className="lab-tag lab-tag--good">Biggest fan</i>}
            {e.key === critic.key && critic.score !== fan.score && <i className="lab-tag lab-tag--bad">Toughest critic</i>}
          </button>
        ))}
      </div>

      <div className="lab-speaker fade-in" key={current.key}>
        <div className="lab-speaker-head">
          <span style={{ fontWeight: 600 }}>{AGENT_META[current.key]?.name}</span>
          <span className="lab-sub"> gives it </span>
          <b style={{ color: scoreTone(current.score) }}>{current.score} out of 10</b>
        </div>
        {rows.map(
          (r) =>
            r.text && (
              <div className="lab-gbg" key={r.label} style={{ "--tone": r.tone }}>
                <span className="lab-gbg-label">{r.label}</span>
                <span className="lab-gbg-text">{r.text}</span>
              </div>
            )
        )}
      </div>
    </div>
  );
}

function Stamps({ card }) {
  if (!card || !(card.great || card.bad || card.gruesome)) return null;
  const items = [
    { label: "The Great", text: card.great, tone: "var(--success)" },
    { label: "The Bad", text: card.bad, tone: "#e0883e" },
    { label: "The Gruesome", text: card.gruesome, tone: "var(--danger)" },
  ].filter((i) => i.text);
  return (
    <div className="lab-stamps">
      {items.map((i) => (
        <div className="lab-stamp" key={i.label} style={{ "--tone": i.tone }}>
          <div className="lab-stamp-label">{i.label}</div>
          <div className="lab-stamp-text">{i.text}</div>
        </div>
      ))}
    </div>
  );
}

function Moat({ moat }) {
  if (!moat || !moat.type) return null;
  return (
    <div className="lab-card">
      <div className="lab-kicker">The moat</div>
      <div className="lab-title">What keeps rivals out: {moat.type}</div>
      {moat.strength != null && (
        <div className="lab-meter" aria-label={`Moat strength ${moat.strength} out of 10`}>
          {Array.from({ length: 10 }, (_, i) => (
            <span key={i} className={i < moat.strength ? "on" : ""} style={{ animationDelay: `${i * 60}ms` }} />
          ))}
          <em>{moat.strength} out of 10</em>
        </div>
      )}
      {moat.story && <p className="lab-body">{moat.story}</p>}
    </div>
  );
}

function Management({ card, mgmt }) {
  const story = card?.management?.story;
  const signals = card?.management?.signals || [];
  if (!story && !mgmt && signals.length === 0) return null;
  const currency = mgmt?.currency;
  const pay = mgmt?.ceo_pay;
  const ins = mgmt?.insiders;
  const prom = mgmt?.promoters;
  const maxPay = pay ? Math.max(pay.latest, ...(pay.earlier || [])) : 0;

  return (
    <div className="lab-card">
      <div className="lab-kicker">Who runs it</div>
      <div className="lab-title">The people, and whose money is on the line</div>
      {story && <p className="lab-body">{story}</p>}

      {signals.length > 0 && (
        <div className="lab-signals">
          {signals.map((s, i) => (
            <span key={i} className={`lab-signal ${s.good ? "lab-signal--good" : "lab-signal--bad"}`}>
              {s.text}
            </span>
          ))}
        </div>
      )}

      {mgmt?.officers && (
        <div className="lab-officers">
          {mgmt.officers.map((o) => (
            <div className="lab-officer" key={o.name}>
              <div>
                <div className="lab-officer-name">{o.name.replace(/^(Mr|Ms|Mrs|Dr)\.?\s+/, "")}</div>
                <div className="lab-sub">{o.title}</div>
              </div>
              <div className="lab-officer-pay">{money(o.pay, currency)}</div>
            </div>
          ))}
        </div>
      )}

      {pay && (
        <div className="lab-mini">
          <div className="lab-mini-title">Chief executive total pay by year</div>
          <div className="lab-bars">
            {[...(pay.earlier || []).slice().reverse(), pay.latest].map((v, i, arr) => (
              <div key={i} className="lab-bar">
                <div style={{ height: `${Math.max(8, (v / maxPay) * 100)}%` }} className={i === arr.length - 1 ? "now" : ""} />
                <span>{money(v, currency)}</span>
              </div>
            ))}
          </div>
          {pay.pct_of_profit != null && (
            <div className="lab-sub">That is {pay.pct_of_profit}% of the company's yearly profit.</div>
          )}
        </div>
      )}

      {ins && (ins.buys > 0 || ins.sells > 0) && (
        <div className="lab-mini">
          <div className="lab-mini-title">Insiders trading their own shares, last 6 months</div>
          <div className="lab-split">
            <span style={{ flexGrow: ins.buys || 0.0001, background: "var(--success)" }}>{ins.buys} buys</span>
            <span style={{ flexGrow: ins.sells || 0.0001, background: "var(--danger)" }}>{ins.sells} sells</span>
          </div>
        </div>
      )}

      {prom && (
        <div className="lab-mini">
          <div className="lab-mini-title">Promoter family ownership</div>
          <div className="lab-big">
            {prom.now}%
            {prom.year_ago != null && prom.year_ago !== prom.now && (
              <small style={{ color: prom.now > prom.year_ago ? "var(--success)" : "var(--danger)" }}>
                {prom.now > prom.year_ago ? " up" : " down"} from {prom.year_ago}% a year ago
              </small>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BusinessLab({ card, facts, scorecards, agents, running }) {
  const order = (agents && agents.length ? agents : AGENT_ORDER).filter((k) => AGENT_META[k]);
  const hasScores = scorecards && Object.keys(scorecards).length > 0;
  if (!card && !facts && !hasScores && !running) return null;

  return (
    <section id="business-lab" className="scroll-anchor lab" style={{ marginBottom: 40 }}>
      <h2 className="lab-heading">The Business Lab</h2>

      {card ? (
        <div className="lab-hero">
          <div className="lab-kicker">In one breath</div>
          <div className="lab-oneline">{card.one_breath}</div>
          {card.analogy && <div className="lab-analogy">{card.analogy}</div>}
          {card.customer && (
            <div className="lab-customer">
              <b>Who pays</b>
              {card.customer}
            </div>
          )}
        </div>
      ) : (
        running && <div className="lab-card lab-wait">Writing the business story while the committee debates…</div>
      )}

      <MoneyFlow flow={facts?.money_flow} />

      {card?.engines?.length > 0 && (
        <div className="lab-card">
          <div className="lab-kicker">How it earns</div>
          <div className="lab-title">The engines behind the revenue</div>
          <div className="lab-engines">
            {card.engines.map((e, i) => (
              <div className="lab-engine" key={e.name}>
                <span className="lab-engine-n">{i + 1}</span>
                <div>
                  <div className="lab-engine-name">{e.name}</div>
                  {e.how && <div className="lab-sub">{e.how}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Scorecards scorecards={scorecards} order={order} />
      <Stamps card={card} />
      <Moat moat={card?.moat} />
      <Management card={card} mgmt={facts?.management} />

      {facts?.wisdom && (
        <div className="lab-quote">
          <div className="lab-quote-text">“{facts.wisdom.quote}”</div>
          <div className="lab-quote-who">{facts.wisdom.who}</div>
          <div className="lab-sub">{facts.wisdom.why}</div>
        </div>
      )}

      {card?.ask_yourself && (
        <div className="lab-ask">
          <b>Ask yourself</b>
          {card.ask_yourself}
        </div>
      )}
    </section>
  );
}
