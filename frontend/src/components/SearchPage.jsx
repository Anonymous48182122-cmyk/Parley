import { useEffect, useState } from "react";
import { MIN_AGENTS } from "../agentMeta.js";
import { loadCommittee, saveCommittee, useOpenResearch } from "../committee.js";
import { currencySymbol } from "../currency.js";
import { countryFor } from "../countryNames.js";
import { listRecent } from "../recent.js";
import CommitteeWall from "./CommitteeWall.jsx";
import Flag from "./Flag.jsx";
import InstallAppButton from "./InstallAppButton.jsx";
import TickerSearchBox from "./TickerSearchBox.jsx";

const QUICK_PICKS = [
  { ticker: "AAPL", name: "Apple", market: "US" },
  { ticker: "NVDA", name: "NVIDIA", market: "US" },
  { ticker: "KO", name: "Coca Cola", market: "US" },
  { ticker: "RELIANCE", name: "Reliance", market: "India" },
  { ticker: "TCS", name: "TCS", market: "India" },
  { ticker: "HDFCBANK", name: "HDFC Bank", market: "India" },
];

const CALL = { BUY: "buy", HOLD: "pass", SELL: "sell" };

function Recent({ items, open }) {
  if (!items.length) return null;
  return (
    <section className="home-block" aria-label="Where you left off">
      <header className="sec-head">
        <h2>Where you left off</h2>
      </header>
      <ul className="rows">
        {items.slice(0, 6).map((r) => (
          <li key={`${r.market}:${r.ticker}`}>
            <button type="button" onClick={() => open(r.ticker, r.market)}>
              <Flag code={countryFor(r)} size={13} />
              <span className="rows-id">
                <b>{r.ticker}</b>
                <em>{r.name}</em>
              </span>
              {r.price != null && (
                <span className="rows-num">
                  {currencySymbol(r.currency || "USD")}
                  {Number(r.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              )}
              {r.verdict && <span className={`tag tag--${CALL[r.verdict] || "pass"}`}>{r.verdict}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function SearchPage() {
  const open = useOpenResearch();
  const [selected, setSelected] = useState(loadCommittee);
  const [recent] = useState(listRecent);

  useEffect(() => saveCommittee(selected), [selected]);

  const ready = selected.size >= MIN_AGENTS;
  const go = (ticker, market) => open(ticker, market, selected);

  return (
    <div className="container home">
      <section className="home-hero">
        <h1>
          Every stock gets <br />
          <em>a hearing.</em>
        </h1>
        <p>Legendary investors read the company, argue it out in front of you, and say what price would change their minds.</p>
        <TickerSearchBox variant="hero" onSelect={go} />
        <div className="quick">
          {QUICK_PICKS.map((q) => (
            <button key={q.ticker} type="button" disabled={!ready} onClick={() => go(q.ticker, q.market)}>
              <Flag code={countryFor(q)} size={11} />
              {q.name}
            </button>
          ))}
        </div>
        <InstallAppButton />
      </section>

      <Recent items={recent} open={go} />
      <CommitteeWall selected={selected} onChange={setSelected} />
    </div>
  );
}
