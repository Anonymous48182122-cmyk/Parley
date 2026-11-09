import { useEffect, useMemo, useRef, useState } from "react";
import { countryFor } from "../countryNames.js";
import { currencySymbol } from "../currency.js";
import { finalStances, tallyFinal } from "../stance.js";
import { businessWord, deriveBrief } from "../brief.js";
import { DepthSwitch, Glance, Story } from "./PlainViews.jsx";
import ConvictionRing from "./ConvictionRing.jsx";
import Flag from "./Flag.jsx";
import MarketSnapshot from "./MarketSnapshot.jsx";
import WhatChanged from "./WhatChanged.jsx";

// The analysis page as a workspace instead of one long scroll. The answer comes first (the Overview), each
// kind of detail gets its own view, and the people reading a live session are taken to the room and told when
// the ruling arrives, without the page ever moving under them.
//
//   Overview   the ruling in brief, four signals that open the detail, the market snapshot
//   Business   how the company makes money and who runs it
//   Books      the balance sheet, at three depths
//   The room   first passes and the debate
//   The ruling the CIO's memo, the price ladder, saving
//   Ask        questions to the committee
//
// The page that owns the data (the live run, or a saved debate) passes in a plain `model` and the heavy views
// as `panels`, so this component only decides what shows, where, and how the answer is summarised.

const VERDICT_COLORS = { BUY: "var(--success)", HOLD: "var(--gold)", SELL: "var(--danger)" };

function formatPrice(price, currency) {
  if (price == null) return null;
  return `${currencySymbol(currency || "USD")}${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function readHash(valid) {
  if (typeof window === "undefined") return null;
  const h = window.location.hash.replace("#", "");
  return valid.includes(h) ? h : null;
}

// ---- the ruling, in brief ------------------------------------------------------------------------------
function VerdictHero({ model, open }) {
  const stances = useMemo(() => finalStances(model.stage1, model.debate), [model.stage1, model.debate]);
  const counts = tallyFinal(stances);
  const moved = Object.values(stances).filter((s) => s.changed).length;
  const decided = Object.keys(stances).length;
  const verdict = model.verdict;
  const color = VERDICT_COLORS[verdict] || "var(--text-dim)";
  const below = (model.priceLevels || []).filter((l) => l.side === "below").sort((a, b) => b.price - a.price)[0];
  const symbol = currencySymbol(model.currency || "USD");

  if (!model.hasMemo) {
    return (
      <div className="ws-hero ws-hero--waiting">
        <div className="lab-kicker">The committee</div>
        <div className="ws-hero-wait">
          {decided > 0
            ? `${decided} first passes are in. The verdict comes after the debate.`
            : "The committee is taking its seats."}
        </div>
        {decided > 0 && (
          <button type="button" className="button-secondary" onClick={() => open("room")}>
            Take a seat at the table
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="ws-hero" style={{ "--verdict": color }}>
      <div className="lab-kicker">The committee's call</div>
      <div className="ws-hero-main">
        <ConvictionRing verdict={verdict} conviction={model.conviction} size={76} />
        <div>
          <div className="ws-hero-verdict">{verdict || "No call"}</div>
          <div className="lab-sub">
            Conviction {model.conviction ?? "unknown"} of 10{model.cioFallback ? ", automatic summary" : ""}
          </div>
        </div>
      </div>
      {decided > 0 && (
        <div className="ws-votes">
          <div className="ws-votes-bar" role="img" aria-label="Final votes">
            {["buy", "pass", "sell", "unclear"].map(
              (k) =>
                counts[k] > 0 && (
                  <span key={k} className={`ws-vote ws-vote--${k}`} style={{ flexGrow: counts[k] }}>
                    {counts[k]}
                  </span>
                )
            )}
          </div>
          <div className="lab-sub">
            {counts.buy} Buy, {counts.pass} Pass, {counts.sell} Sell
            {counts.unclear ? `, ${counts.unclear} undecided` : ""}
            {moved > 0 ? `. ${moved} changed their mind in the debate.` : "."}
          </div>
        </div>
      )}
      {below && (
        <div className="ws-hero-level">
          The first members step in near <b>{symbol}{below.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}</b>, {Math.abs(Math.round(below.pct))}% below today.
        </div>
      )}
      <button type="button" className="button-primary ws-hero-cta" onClick={() => open("ruling")}>
        Read the CIO's memo
      </button>
    </div>
  );
}

// ---- four signals that open the detail ------------------------------------------------------------------
function Signals({ model, open }) {
  const scores = Object.values(model.scorecards || {}).map((c) => c.score).filter(Boolean);
  const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  const bs = model.balanceSheet;
  const decided = Object.keys(model.stage1 || {}).length;
  const below = (model.priceLevels || []).filter((l) => l.side === "below").sort((a, b) => b.price - a.price)[0];
  const above = (model.priceLevels || []).filter((l) => l.side === "above").sort((a, b) => a.price - b.price)[0];
  const tones = { strong: "var(--success)", mixed: "var(--gold)", weak: "var(--danger)", unknown: "var(--text-faint)" };

  const tiles = [];
  if (avg != null || model.businessCard) {
    tiles.push({
      id: "business", kicker: "The Lab",
      big: avg != null ? `${avg.toFixed(1)}/10` : "Read it",
      line: avg != null ? businessWord(avg) : model.businessCard?.one_breath,
      color: avg != null ? (avg >= 6.5 ? "var(--success)" : avg >= 5 ? "var(--gold)" : "var(--danger)") : "var(--gold)",
    });
  }
  if (bs) {
    tiles.push({ id: "books", kicker: "The Ledger", big: bs.verdict?.tone ? bs.verdict.tone[0].toUpperCase() + bs.verdict.tone.slice(1) : "Read it",
      line: (() => { const parts = (bs.verdict?.text || "").split(". "); return parts[1] || parts[0]; })(), color: tones[bs.verdict?.tone] || tones.unknown });
  }
  if (decided > 0) {
    tiles.push({ id: "room", kicker: "The Table", big: `${decided} voices`, line: (model.debate || []).length ? `${model.debate.length} debate turns` : "First passes in", color: "var(--gold)" });
  }
  if (below || above) {
    tiles.push({ id: "ruling", kicker: "The price", big: formatPrice(model.price, model.currency) || "Levels",
      line: below ? `Buyers start near ${formatPrice(below.price, model.currency)}` : `Sellers start near ${formatPrice(above.price, model.currency)}`, color: "var(--gold)" });
  }
  if (tiles.length === 0) return null;
  return (
    <div className="ws-tiles">
      {tiles.map((t) => (
        <button type="button" key={t.id} className="ws-tile" onClick={() => open(t.id)} style={{ "--tile": t.color }}>
          <span className="ws-tile-kicker">{t.kicker}</span>
          <span className="ws-tile-big">{t.big}</span>
          <span className="ws-tile-line">{t.line}</span>
          <span className="ws-tile-go" aria-hidden="true">Open</span>
        </button>
      ))}
    </div>
  );
}

// ---- the workspace -----------------------------------------------------------------------------------------
export default function AnalysisWorkspace({ model, panels, liveTop, snapshotSkeleton, previousEntry, job, live }) {
  const running = model.status === "running";
  const tabs = useMemo(() => {
    const roomCount = (model.debate || []).length;
    return [
      { id: "overview", label: "The Brief" },
      model.hasBusiness && { id: "business", label: "The Lab" },
      model.balanceSheet && { id: "books", label: "The Ledger" },
      Object.keys(model.stage1 || {}).length > 0 && { id: "room", label: "The Table", live: running && model.stage === "debate", count: roomCount || null },
      model.hasMemo && { id: "ruling", label: "The Verdict", done: true },
      (live ? (Object.keys(model.stage1 || {}).length > 0 || model.status === "complete") : (model.userChat || []).length > 0) && { id: "ask", label: "Your Seat" },
    ].filter(Boolean);
  }, [model, running, live]);
  const ids = tabs.map((t) => t.id);

  const [tab, setTab] = useState(() => readHash(ids) || "overview");
  const picked = useRef(!!readHash(ids));
  // how much time the reader has: ten seconds, a minute, or all of it. A link to a tab means all of it.
  const [depth, setDepthState] = useState(() => {
    if (readHash(ids)) return "full";
    try {
      const v = localStorage.getItem("parley.depth");
      return v === "story" || v === "full" || v === "glance" ? v : "glance";
    } catch {
      return "glance";
    }
  });
  function setDepth(next) {
    setDepthState(next);
    try {
      localStorage.setItem("parley.depth", next);
    } catch {
      // remembering the choice is a nicety
    }
  }
  const brief = useMemo(() => deriveBrief(model), [model]);
  const memoAtStart = useRef(model.hasMemo);
  const [toastGone, setToastGone] = useState(false);
  const topRef = useRef(null);

  // a tab that disappears (a run restarted) falls back to the overview
  useEffect(() => {
    if (!ids.includes(tab)) setTab("overview");
  }, [ids, tab]);

  // someone watching a live run is taken to the room once, as soon as there is something to watch
  useEffect(() => {
    if (live && running && depth === "full" && !picked.current && tab === "overview" && ids.includes("room")) setTab("room");
  }, [live, running, depth, tab, ids]);

  function open(id) {
    picked.current = true;
    if (depth !== "full") setDepth("full");
    setTab(id);
    try {
      window.history.replaceState(window.history.state, "", `#${id}`);
    } catch {
      // the address bar is a nicety
    }
    const bar = topRef.current;
    if (bar && bar.getBoundingClientRect().top < 60) window.scrollTo({ top: window.scrollY + bar.getBoundingClientRect().top - 58, behavior: "smooth" });
  }

  // the quick views need a ruling; until then they show the live session and say when the brief will arrive
  const waiting = model.hasMemo ? null : (
    <>
      {liveTop}
      <div className="ws-hero ws-hero--waiting">
        <div className="lab-kicker">The committee</div>
        <div className="ws-hero-wait">
          {running
            ? "The committee is still at work. Your quick brief appears here the moment they finish."
            : "This session did not reach a ruling, so there is no quick brief."}
        </div>
        <button type="button" className="button-secondary" onClick={() => setDepth("full")}>
          {running ? "Watch them work" : "Show me what they said"}
        </button>
      </div>
    </>
  );

  const showToast = live && depth === "full" && model.hasMemo && !memoAtStart.current && tab !== "ruling" && tab !== "overview" && !toastGone;
  const verdictColor = VERDICT_COLORS[model.verdict] || "var(--text-dim)";
  const country = model.country || countryFor({ market: model.market });

  return (
    <div className="ws">
      <header className="ws-head">
        <div className="ws-id">
          <h1 className="ticker">{String(model.ticker).toUpperCase()}</h1>
          <Flag code={country} size={15} />
          {model.market === "Global" && model.exchange && <span className="ws-exchange">{model.exchange}</span>}
        </div>
        {model.name && model.name !== model.ticker && <div className="ws-name">{model.name}</div>}
        <div className="ws-head-row">
          {model.price != null && <span className="ws-price">{formatPrice(model.price, model.currency)}</span>}
          {model.hasMemo && model.verdict && (
            <button type="button" className="ws-chip" style={{ color: verdictColor, borderColor: verdictColor }} onClick={() => open("ruling")}>
              {model.verdict} {model.conviction != null ? `· ${model.conviction}/10` : ""}
            </button>
          )}
          {running && <span className="ws-chip ws-chip--live">Live</span>}
        </div>
      </header>

      <DepthSwitch depth={depth} setDepth={setDepth} />

      {depth === "glance" && <Glance model={model} brief={brief} go={setDepth} waiting={waiting} />}
      {depth === "story" && <Story model={model} brief={brief} go={setDepth} waiting={waiting} />}

      {depth === "full" && (
      <>
      <div className="ws-tabbar" ref={topRef} role="tablist" aria-label="Parts of the analysis">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={`ws-tab${tab === t.id ? " ws-tab--on" : ""}`} onClick={() => open(t.id)}>
            {t.label}
            {t.live && <i className="ws-pulse" aria-label="live" />}
            {t.count ? <em>{t.count}</em> : null}
            {t.done && tab !== t.id && <i className="ws-new" aria-label="ready" />}
          </button>
        ))}
      </div>

      <div className="ws-body" key={tab}>
        {tab === "overview" && (
          <div className="fade-in">
            {liveTop}
            <VerdictHero model={model} open={open} />
            <Signals model={model} open={open} />
            {model.marketData ? <MarketSnapshot data={model.marketData} /> : running && snapshotSkeleton}
            {previousEntry && <WhatChanged previous={previousEntry} current={job} />}
          </div>
        )}
        {tab === "business" && <div className="fade-in">{panels.business}</div>}
        {tab === "books" && <div className="fade-in">{panels.books}</div>}
        {tab === "room" && <div className="fade-in">{panels.room}</div>}
        {tab === "ruling" && <div className="fade-in">{panels.ruling}</div>}
        {tab === "ask" && <div className="fade-in">{panels.ask}</div>}
      </div>
      </>
      )}

      {showToast && (
        <div className="ws-toast fade-in" role="status">
          <span>The verdict is in.</span>
          <button type="button" className="button-primary" onClick={() => open("ruling")}>Read it</button>
          <button type="button" className="ws-toast-x" onClick={() => setToastGone(true)} aria-label="Dismiss">×</button>
        </div>
      )}
    </div>
  );
}
