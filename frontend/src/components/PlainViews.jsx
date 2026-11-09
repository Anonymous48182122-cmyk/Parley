import "../plainviews.css";
import { useEffect, useRef, useState } from "react";
import { agentColor, agentName } from "../agentMeta.js";
import { spokenBrief } from "../brief.js";
import { currencySymbol } from "../currency.js";
import AgentAvatar from "./AgentAvatar.jsx";
import ConvictionRing from "./ConvictionRing.jsx";

// The two quick ways in. "Glance" is one screen you can take in within ten seconds. "Story" is a short run of
// swipeable cards, one idea each, for the minute after that. Both read from the same `brief` (src/brief.js),
// and both end by pointing at the full analysis for anyone who wants to keep going.

const VERDICT_COLORS = { BUY: "var(--success)", HOLD: "var(--gold)", SELL: "var(--danger)" };
const TONE_WORD = { good: "Yes", ok: "Maybe", bad: "No", unknown: "Unclear" };
const SIDE = {
  buy: { label: "For", color: "var(--success)" },
  pass: { label: "Not sure", color: "var(--gold)" },
  sell: { label: "Against", color: "var(--danger)" },
  unclear: { label: "Undecided", color: "var(--text-faint)" },
};

export function Lights({ lights }) {
  return (
    <div className="pv-lights">
      {lights.map((l) => (
        <div key={l.id} className={`pv-light pv-light--${l.tone}`}>
          <span className="pv-light-dot" aria-hidden="true" />
          <span className="pv-light-q">{l.question}</span>
          <b className="pv-light-a">{TONE_WORD[l.tone]}</b>
          <span className="pv-light-line">{l.line}</span>
        </div>
      ))}
    </div>
  );
}

function VoteBar({ counts }) {
  return (
    <div className="ws-votes-bar" role="img" aria-label="How the committee voted">
      {["buy", "pass", "sell", "unclear"].map(
        (k) =>
          counts[k] > 0 && (
            <span key={k} className={`ws-vote ws-vote--${k}`} style={{ flexGrow: counts[k] }}>
              {counts[k]}
            </span>
          )
      )}
    </div>
  );
}

function voteWords(brief) {
  const c = brief.counts;
  return `${c.buy} for, ${c.pass} not sure, ${c.sell} against${c.unclear ? `, ${c.unclear} undecided` : ""}`;
}

// Reads the brief aloud with the browser's own voice: free, private, and nothing to install.
function useSpeech() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => supported && window.speechSynthesis.cancel(), [supported]);
  function toggle(text) {
    if (!supported) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.02;
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
    setSpeaking(true);
  }
  return { supported, speaking, toggle };
}

function ListenButton({ model, brief, className = "button-secondary" }) {
  const speech = useSpeech();
  if (!speech.supported) return null;
  return (
    <button type="button" className={className} onClick={() => speech.toggle(spokenBrief(model, brief))}>
      {speech.speaking ? "Stop" : "Hear it in 40 seconds"}
    </button>
  );
}

// ---- Glance: one screen ------------------------------------------------------------------------------------
export function Glance({ model, brief, go, waiting }) {
  const color = VERDICT_COLORS[model.verdict] || "var(--text-dim)";
  if (waiting) return waiting;
  return (
    <div className="pv-glance fade-in" style={{ "--verdict": color }}>
      <div className="lab-kicker">The committee's call</div>
      <div className="pv-glance-top">
        <ConvictionRing verdict={model.verdict} conviction={model.conviction} size={84} />
        <div>
          <div className="ws-hero-verdict">{model.verdict || "No call"}</div>
          <div className="lab-sub">
            Sure about it: {model.conviction ?? "unknown"} out of 10{model.cioFallback ? ", automatic summary" : ""}
          </div>
        </div>
      </div>
      <p className="pv-headline">{brief.headline}</p>

      <Lights lights={brief.lights} />

      {brief.decided > 0 && (
        <div className="ws-votes">
          <VoteBar counts={brief.counts} />
          <div className="lab-sub">
            {voteWords(brief)}
            {brief.moved > 0 ? `. ${brief.moved} changed their mind in the debate.` : "."}
          </div>
        </div>
      )}

      {brief.changeMind && (
        <div className="pv-change">
          <b>What would change their mind</b>
          {brief.changeMind}
        </div>
      )}

      <div className="pv-actions">
        <button type="button" className="button-primary" onClick={() => go("story")}>
          Tell me the story, 1 minute
        </button>
        <button type="button" className="button-secondary" onClick={() => go("full")}>
          Show me everything
        </button>
      </div>
      <div className="pv-listen">
        <ListenButton model={model} brief={brief} />
      </div>
      <div className="pv-foot">The committee's view, not advice.</div>
    </div>
  );
}

// ---- Story: swipeable cards --------------------------------------------------------------------------------
function Member({ m }) {
  return (
    <div className="pv-member">
      <AgentAvatar agentKey={m.agent} size="sm" />
      <div>
        <b style={{ color: agentColor(m.agent) }}>{agentName(m.agent)}</b>
        {m.changed && <em> changed their mind</em>}
        {m.line && <span>{m.line}</span>}
      </div>
    </div>
  );
}

function buildCards(model, brief, go) {
  const color = VERDICT_COLORS[model.verdict] || "var(--text-dim)";
  const cards = [];

  cards.push({
    id: "call",
    title: "The call",
    node: (
      <>
        <div className="pv-card-ring" style={{ "--verdict": color }}>
          <ConvictionRing verdict={model.verdict} conviction={model.conviction} size={96} />
          <div className="ws-hero-verdict" style={{ color }}>{model.verdict || "No call"}</div>
        </div>
        <p className="pv-headline pv-headline--big">{brief.headline}</p>
        <Lights lights={brief.lights} />
      </>
    ),
  });

  const card = model.businessCard;
  if (card?.one_breath) {
    cards.push({
      id: "business",
      title: "What it is",
      node: (
        <>
          <p className="pv-headline pv-headline--big">{card.one_breath}</p>
          {card.analogy && <p className="pv-analogy">{card.analogy}</p>}
          {card.engines?.length > 0 && (
            <div className="pv-chips">
              {card.engines.map((e) => (
                <span key={e.name} className="pv-chip" title={e.how}>
                  {e.name}
                </span>
              ))}
            </div>
          )}
          {card.moat?.type && card.moat.type !== "Nothing special" && (
            <div className="pv-change">
              <b>Why rivals struggle to copy it</b>
              {card.moat.story || card.moat.type}
            </div>
          )}
        </>
      ),
    });
  }

  if (brief.decided > 0) {
    const groups = ["buy", "pass", "sell"].map((k) => ({ k, items: brief.members.filter((m) => m.side === k) })).filter((g) => g.items.length);
    cards.push({
      id: "table",
      title: "Who said what",
      node: (
        <>
          <VoteBar counts={brief.counts} />
          <div className="lab-sub" style={{ margin: "8px 0 14px" }}>{voteWords(brief)}</div>
          <div className="pv-table">
            {groups.map((g) => (
              <div key={g.k} className="pv-side" style={{ "--side": SIDE[g.k].color }}>
                <div className="pv-side-head">{SIDE[g.k].label}</div>
                {g.items.map((m) => (
                  <Member key={m.agent} m={m} />
                ))}
              </div>
            ))}
          </div>
        </>
      ),
    });
  }

  if (brief.forList.length || brief.againstList.length) {
    cards.push({
      id: "why",
      title: "Why yes, why no",
      node: (
        <div className="pv-why">
          {brief.forList.length > 0 && (
            <div className="pv-why-col pv-why-col--for">
              <div className="pv-why-head">What they like</div>
              <ul>
                {brief.forList.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          )}
          {brief.againstList.length > 0 && (
            <div className="pv-why-col pv-why-col--against">
              <div className="pv-why-head">What worries them</div>
              <ul>
                {brief.againstList.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ),
    });
  }

  const bs = model.balanceSheet;
  if (bs?.metrics?.length) {
    const basic = bs.metrics.filter((m) => m.level === "basic").slice(0, 3);
    const tones = { strong: "var(--success)", mixed: "var(--gold)", weak: "var(--danger)" };
    const stat = { good: ["Strong", "var(--success)"], watch: ["Watch", "var(--gold)"], bad: ["Weak", "var(--danger)"], unknown: ["Context", "var(--text-faint)"] };
    cards.push({
      id: "safety",
      title: "Can it handle a bad year?",
      node: (
        <>
          <div className="pv-change" style={{ borderColor: tones[bs.verdict?.tone] || "var(--border-strong)" }}>
            {{ strong: "Its finances look solid. A bad year should not hurt it much.", mixed: "Its finances have strengths and some worries. A bad year would test it.", weak: "Its finances look stretched. A bad year could hurt it badly." }[bs.verdict?.tone] || "There is not enough data to judge its finances."}
          </div>
          <div className="pv-stats">
            {basic.map((m) => {
              const [word, c] = stat[m.status] || stat.unknown;
              return (
                <div key={m.id} className="pv-stat">
                  <span className="pv-stat-label">{m.label}</span>
                  <b>{m.display}</b>
                  <span className="pv-stat-chip" style={{ color: c, borderColor: c }}>{word}</span>
                </div>
              );
            })}
          </div>
        </>
      ),
    });
  }

  if (model.price != null) {
    const sym = currencySymbol(model.currency || "USD");
    const fmt = (n) => `${sym}${Number(n).toLocaleString(undefined, { maximumFractionDigits: n >= 100 ? 0 : 2 })}`;
    const above = (model.priceLevels || []).filter((l) => l.side === "above").sort((a, b) => a.price - b.price)[0];
    cards.push({
      id: "price",
      title: "The price",
      node: (
        <div className="pv-price">
          {above && (
            <div className="pv-price-row pv-price-row--up">
              <span>Sellers step in near</span>
              <b>{fmt(above.price)}</b>
              <em>{Math.round(above.pct)}% above today</em>
            </div>
          )}
          <div className="pv-price-row pv-price-row--now">
            <span>Today</span>
            <b>{fmt(model.price)}</b>
          </div>
          {brief.zone && (
            <div className="pv-price-row pv-price-row--down">
              <span>Buyers step in near</span>
              <b>{fmt(brief.zone.price)}</b>
              <em>{Math.abs(Math.round(brief.zone.pct))}% below today</em>
            </div>
          )}
          {!above && !brief.zone && <div className="lab-sub">The members did not name a price they would act at.</div>}
        </div>
      ),
    });
  }

  const quote = model.wisdom;
  cards.push({
    id: "end",
    title: "In short",
    node: (
      <>
        {brief.changeMind && (
          <div className="pv-change">
            <b>What would change their mind</b>
            {brief.changeMind}
          </div>
        )}
        {quote?.quote && (
          <blockquote className="pv-quote">
            “{quote.quote}”
            <cite>{quote.who}</cite>
          </blockquote>
        )}
        <div className="pv-actions">
          <ListenButton model={model} brief={brief} className="button-primary" />
          <button type="button" className="button-secondary" onClick={() => go("full")}>
            Read everything
          </button>
        </div>
        <div className="pv-foot">The committee's view, not advice.</div>
      </>
    ),
  });

  return cards;
}

export function Story({ model, brief, go, waiting }) {
  const [i, setI] = useState(0);
  const touch = useRef(null);
  const cards = waiting ? [] : buildCards(model, brief, go);
  const last = cards.length - 1;

  useEffect(() => {
    function key(e) {
      if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
      if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, last));
      if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [last]);

  if (waiting) return waiting;
  const current = cards[Math.min(i, last)];

  return (
    <div
      className="pv-story fade-in"
      onTouchStart={(e) => (touch.current = e.touches[0].clientX)}
      onTouchEnd={(e) => {
        if (touch.current == null) return;
        const dx = e.changedTouches[0].clientX - touch.current;
        touch.current = null;
        if (dx < -50) setI((n) => Math.min(n + 1, last));
        if (dx > 50) setI((n) => Math.max(n - 1, 0));
      }}
    >
      <div className="pv-dots" role="tablist" aria-label="Story cards">
        {cards.map((c, n) => (
          <button key={c.id} type="button" role="tab" aria-selected={n === i} aria-label={c.title} className={`pv-dot${n === i ? " pv-dot--on" : n < i ? " pv-dot--seen" : ""}`} onClick={() => setI(n)} />
        ))}
      </div>
      <div className="pv-card" key={current.id}>
        <div className="lab-kicker">{current.title}</div>
        {current.node}
      </div>
      <div className="pv-nav">
        <button type="button" className="button-secondary" disabled={i === 0} onClick={() => setI((n) => Math.max(n - 1, 0))}>
          Back
        </button>
        <span className="pv-count">{Math.min(i, last) + 1} of {cards.length}</span>
        <button type="button" className="button-primary" disabled={i >= last} onClick={() => setI((n) => Math.min(n + 1, last))}>
          Next
        </button>
      </div>
    </div>
  );
}

// ---- the way in: how much time do you have -----------------------------------------------------------------
export const DEPTHS = [
  { id: "glance", label: "10 seconds" },
  { id: "story", label: "1 minute" },
  { id: "full", label: "All of it" },
];

export function DepthSwitch({ depth, setDepth }) {
  return (
    <div className="pv-depth" role="tablist" aria-label="How much time do you have?">
      <span className="pv-depth-q">How long do you have?</span>
      <div className="pv-depth-opts">
        {DEPTHS.map((d) => (
          <button key={d.id} type="button" role="tab" aria-selected={depth === d.id} className={`pv-depth-opt${depth === d.id ? " pv-depth-opt--on" : ""}`} onClick={() => setDepth(d.id)}>
            {d.label}
          </button>
        ))}
      </div>
    </div>
  );
}

