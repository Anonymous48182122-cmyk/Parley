import { useEffect, useMemo, useRef, useState } from "react";
import { countryFor } from "../countryNames.js";
import { currencySymbol } from "../currency.js";
import { deriveBrief } from "../brief.js";
import { addRecent } from "../recent.js";
import { useBrand } from "../useBrand.js";
import Brief from "./Brief.jsx";
import CaseFile from "./CaseFile.jsx";
import CompanyLogo from "./CompanyLogo.jsx";
import Flag from "./Flag.jsx";
import Floor from "./Floor.jsx";
import MarketSnapshot from "./MarketSnapshot.jsx";
import WhatChanged from "./WhatChanged.jsx";

// A company's page. The Floor comes first: the committee as a room whose members move when the reader moves the
// price. Below it, each kind of detail has its own view, so nobody has to scroll past what they did not ask for.
//
//   The Brief    three plain checks, the case for and against, the figures
//   The Lab      how the company makes money and who runs it
//   The Ledger   the balance sheet, at three depths
//   The Table    first passes and the debate
//   The Verdict  the CIO's memo, the price ladder, saving
//   Your Seat    questions to the committee
//
// The page that owns the data (a live run, or a saved debate) passes a plain `model` and the heavy views as
// `panels`, so this component only decides what shows and where.

function formatPrice(price, currency) {
  if (price == null) return null;
  return `${currencySymbol(currency || "USD")}${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function readHash(valid) {
  if (typeof window === "undefined") return null;
  const h = window.location.hash.replace("#", "");
  return valid.includes(h) ? h : null;
}

export default function AnalysisWorkspace({ model, panels, liveTop, snapshotSkeleton, previousEntry, job, live }) {
  const running = model.status === "running";
  const tabs = useMemo(() => {
    const roomCount = (model.debate || []).length;
    const heard = Object.keys(model.stage1 || {}).length > 0;
    return [
      { id: "overview", label: "The Brief" },
      model.hasBusiness && { id: "business", label: "The Lab" },
      model.balanceSheet && { id: "books", label: "The Ledger" },
      heard && { id: "room", label: "The Table", live: running && model.stage === "debate", count: roomCount || null },
      model.hasMemo && { id: "ruling", label: "The Verdict" },
      (live ? heard || model.status === "complete" : (model.userChat || []).length > 0) && { id: "ask", label: "Your Seat" },
    ].filter(Boolean);
  }, [model, running, live]);
  const ids = tabs.map((t) => t.id);

  const [tab, setTab] = useState(() => readHash(ids) || "overview");
  const topRef = useRef(null);
  const brief = useMemo(() => deriveBrief(model), [model]);
  const brand = useBrand(model);
  const md = model.marketData || {};
  const yearChange = md.technicals?.ret_1y;
  const country = model.country || countryFor({ market: model.market });
  const speaking = running && model.stage === "debate" ? model.speaking : null;

  // a tab that disappears (a run restarted) falls back to the brief
  useEffect(() => {
    if (!ids.includes(tab)) setTab("overview");
  }, [ids, tab]);

  // remember what was looked at, for the home page's "where you left off"
  useEffect(() => {
    if (!live || !md.name) return;
    addRecent({
      ticker: String(model.ticker).toUpperCase(), name: md.name, market: model.market, country: model.country,
      verdict: model.hasMemo ? model.verdict : null, price: model.price, currency: model.currency,
    });
  }, [live, md.name, model.ticker, model.market, model.hasMemo, model.verdict, model.price]); // eslint-disable-line react-hooks/exhaustive-deps

  function open(id) {
    setTab(id);
    try {
      window.history.replaceState(window.history.state, "", `#${id}`);
    } catch {
      // the address bar is a nicety
    }
    const bar = topRef.current;
    if (bar && bar.getBoundingClientRect().top < 66) window.scrollTo({ top: window.scrollY + bar.getBoundingClientRect().top - 64, behavior: "smooth" });
  }

  return (
    <div className={`ws${running ? " ws--live" : ""}`}>
      <header className="stock">
        <CompanyLogo brand={brand} name={model.name || model.ticker} size={52} wide />
        <div className="stock-id">
          <h1>{model.name || String(model.ticker).toUpperCase()}</h1>
          <div className="stock-meta">
            <span className="ticker">{String(model.ticker).toUpperCase()}</span>
            <Flag code={country} size={12} />
            {(model.exchange || md.sector) && <span>{[model.exchange, md.sector && md.sector !== "N/A" ? md.sector : null].filter(Boolean).join(", ")}</span>}
          </div>
        </div>
        <div className="stock-quote">
          {model.price != null && <div className="stock-price">{formatPrice(model.price, model.currency)}</div>}
          {yearChange != null && (
            <div className={`stock-change ${yearChange >= 0 ? "up" : "down"}`}>
              {yearChange >= 0 ? "+" : ""}
              {yearChange.toFixed(1)}% in a year
            </div>
          )}
        </div>
        <div className="stock-actions">
          <CaseFile model={model} brand={brand} onFull={() => open("overview")} />
        </div>
      </header>

      {liveTop}

      <Floor model={model} brief={brief} speaking={speaking} />

      <div className="ws-tabbar" ref={topRef} role="tablist" aria-label="Parts of the analysis">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={`ws-tab${tab === t.id ? " ws-tab--on" : ""}`} onClick={() => open(t.id)}>
            {t.label}
            {t.live && <i className="ws-pulse" aria-label="live" />}
            {t.count ? <em>{t.count}</em> : null}
          </button>
        ))}
      </div>

      <div className="ws-body" key={tab}>
        {tab === "overview" && (
          <div className="fade-in">
            <Brief model={model} brief={brief} />
            {model.marketData ? <MarketSnapshot data={model.marketData} compact /> : running && snapshotSkeleton}
            {previousEntry && <WhatChanged previous={previousEntry} current={job} />}
          </div>
        )}
        {tab === "business" && <div className="fade-in">{panels.business}</div>}
        {tab === "books" && <div className="fade-in">{panels.books}</div>}
        {tab === "room" && <div className="fade-in">{panels.room}</div>}
        {tab === "ruling" && <div className="fade-in">{panels.ruling}</div>}
        {tab === "ask" && <div className="fade-in">{panels.ask}</div>}
      </div>
    </div>
  );
}
