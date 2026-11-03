import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { deleteHistoryEntry, getPrices, listHistory } from "../api.js";
import ConvictionRing from "./ConvictionRing.jsx";
import Sparkline from "./Sparkline.jsx";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "BUY", label: "Buy" },
  { id: "HOLD", label: "Hold" },
  { id: "SELL", label: "Sell" },
];

const VERDICT_COLORS = { BUY: "var(--success)", HOLD: "var(--gold)", SELL: "var(--danger)" };

function excerpt(text, maxLen = 150) {
  if (!text) return "";
  const clean = text.replace(/[#*_]/g, "").replace(/\s+/g, " ").trim();
  return clean.length > maxLen ? clean.slice(0, maxLen).trimEnd() + "…" : clean;
}

function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

// How a saved call has done since it was made. For a Buy, up is right; for a Sell, down is right; a Hold has
// no right or wrong, so it is shown without a colour.
function sinceCall(entry, prices) {
  const then = entry.market_data?.price;
  const now = prices?.[`${entry.ticker.toUpperCase()}:${entry.market === "India" ? "India" : "US"}`];
  if (!then || !now) return null;
  const pct = (now / then - 1) * 100;
  const days = (Date.now() - new Date(entry.created_at).getTime()) / 86400000;
  const right = entry.verdict === "BUY" ? pct > 0 : entry.verdict === "SELL" ? pct < 0 : null;
  return { pct, days, right, counts: days >= 3 && right !== null };
}

function HistoryCard({ entry, onDelete, move }) {
  const [confirming, setConfirming] = useState(false);
  const timer = useRef(null);
  const closes = entry.market_data?.technicals?.closes;
  const currency = entry.market_data?.price_currency ?? entry.market_data?.currency;
  const symbol = { USD: "$", INR: "₹" }[currency] || "";
  const color = VERDICT_COLORS[entry.verdict] || "var(--text-dim)";

  useEffect(() => () => clearTimeout(timer.current), []);

  // A first click only asks; the second, within a few seconds, deletes. A stray tap can't
  // remove a saved debate.
  function handleDelete() {
    if (!confirming) {
      setConfirming(true);
      timer.current = setTimeout(() => setConfirming(false), 3500);
      return;
    }
    clearTimeout(timer.current);
    onDelete(entry.id);
  }

  return (
    <div className="history-card card fade-in">
      <Link to={`/history/${entry.id}`} className="history-card-link">
        <ConvictionRing verdict={entry.verdict} conviction={entry.conviction} />
        <div className="history-card-main">
          <div className="history-card-head">
            <span className="ticker history-ticker">{entry.ticker}</span>
            {entry.market && <span className="pill" style={{ fontSize: "0.68rem", padding: "3px 10px" }}>{entry.market}</span>}
            {move && (
              <span
                className="history-since"
                style={{ color: move.right === null ? "var(--text-dim)" : move.right ? "var(--success)" : "var(--danger)" }}
                title="Share price change since this debate was saved"
              >
                {move.pct > 0 ? "+" : ""}
                {move.pct.toFixed(1)}% since
              </span>
            )}
            <span className="history-verdict" style={{ color }}>
              {entry.verdict || "No call"}
            </span>
            <span className="history-date">{formatDate(entry.created_at)}</span>
          </div>
          <div className="history-excerpt">{excerpt(entry.cio_memo)}</div>
        </div>
        {closes?.length > 5 && (
          <div className="history-chart">
            <Sparkline values={closes} symbol={symbol} height={46} compact />
            {entry.market_data?.price != null && (
              <div className="history-price">
                {symbol}
                {entry.market_data.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                <span> when saved</span>
              </div>
            )}
          </div>
        )}
      </Link>
      <button
        type="button"
        className={`history-delete${confirming ? " history-delete--confirm" : ""}`}
        onClick={handleDelete}
        aria-label={confirming ? `Confirm deleting ${entry.ticker}` : `Delete ${entry.ticker}`}
      >
        {confirming ? "Sure?" : "Delete"}
      </button>
    </div>
  );
}

export default function HistoryPage() {
  const { session } = useAuth();
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!session) return;
    listHistory(session.access_token)
      .then(setEntries)
      .catch((err) => setError(err.message));
  }, [session]);

  async function handleDelete(id) {
    try {
      await deleteHistoryEntry(session.access_token, id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  return <HistoryView entries={entries} error={error} onDelete={handleDelete} />;
}

export function HistoryView({ entries, error, onDelete }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [prices, setPrices] = useState({});

  // today's prices for the tickers saved here, to show how each call has aged; best effort
  useEffect(() => {
    if (!entries?.length) return;
    const items = [...new Set(entries.filter((e) => e.market_data?.price).map((e) => `${e.ticker.toUpperCase()}:${e.market === "India" ? "India" : "US"}`))];
    if (items.length === 0) return;
    getPrices(items.slice(0, 40)).then(setPrices).catch(() => {});
  }, [entries]);

  const record = useMemo(() => {
    const scored = (entries || []).map((e) => ({ e, m: sinceCall(e, prices) })).filter((x) => x.m?.counts);
    if (scored.length === 0) return null;
    const avg = (v) => {
      const xs = scored.filter((x) => x.e.verdict === v).map((x) => x.m.pct);
      return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
    };
    return { total: scored.length, right: scored.filter((x) => x.m.right).length, buyAvg: avg("BUY"), sellAvg: avg("SELL") };
  }, [entries, prices]);

  const counts = useMemo(() => {
    const c = { BUY: 0, HOLD: 0, SELL: 0 };
    (entries || []).forEach((e) => {
      if (c[e.verdict] !== undefined) c[e.verdict] += 1;
    });
    return c;
  }, [entries]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (entries || []).filter(
      (e) => (filter === "all" || e.verdict === filter) && (!q || e.ticker.toLowerCase().includes(q))
    );
  }, [entries, filter, query]);

  const total = entries?.length ?? 0;

  return (
    <div className="container">
      <Link to="/" style={{ color: "var(--text-faint)", fontSize: "0.85rem" }}>
        ← back to search
      </Link>

      <h1 style={{ fontSize: "2rem", margin: "18px 0 6px" }}>Your saved debates</h1>
      <p style={{ color: "var(--text-dim)", fontSize: "0.9rem", margin: "0 0 26px" }}>
        Every call the committee has made for you, kept so you can see how it aged.
      </p>

      {error && (
        <div className="card" style={{ borderColor: "var(--danger)", marginBottom: 20, color: "var(--danger)" }}>
          {error}
        </div>
      )}

      {entries === null && !error && (
        <div className="history-list" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card" style={{ display: "flex", gap: 14, alignItems: "center" }}>
              <div className="skeleton" style={{ width: 52, height: 52, borderRadius: "50%" }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton" style={{ height: 14, width: "30%", marginBottom: 10 }} />
                <div className="skeleton" style={{ height: 10, width: "80%" }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {entries?.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: "52px 24px" }}>
          <div style={{ fontSize: "1.05rem", fontWeight: 600, marginBottom: 8 }}>Nothing saved yet</div>
          <div style={{ color: "var(--text-dim)", fontSize: "0.92rem", lineHeight: 1.6, marginBottom: 20 }}>
            Run a committee session and press <span style={{ color: "var(--gold)" }}>Save to History</span> once
            the CIO memo is ready.
          </div>
          <Link to="/" className="button-primary" style={{ display: "inline-block" }}>
            Convene a committee
          </Link>
        </div>
      )}

      {total > 0 && (
        <>
          <div className="history-summary">
            <div>
              <div className="history-summary-number">{total}</div>
              <div className="history-summary-label">{total === 1 ? "saved debate" : "saved debates"}</div>
            </div>
            {["BUY", "HOLD", "SELL"].map((v) => (
              <div key={v}>
                <div className="history-summary-number" style={{ color: VERDICT_COLORS[v] }}>
                  {counts[v]}
                </div>
                <div className="history-summary-label">{v === "BUY" ? "Buy" : v === "HOLD" ? "Hold" : "Sell"}</div>
              </div>
            ))}
          </div>

          {record && (
            <div className="history-record">
              <div className="lab-kicker">Track record</div>
              <div className="history-record-line">
                <b>{record.right}</b> of <b>{record.total}</b> Buy and Sell calls have gone the right way since you saved them.
              </div>
              <div className="lab-sub">
                {record.buyAvg !== null && <>Buy calls: {record.buyAvg > 0 ? "+" : ""}{record.buyAvg.toFixed(1)}% on average. </>}
                {record.sellAvg !== null && <>Sell calls: {record.sellAvg > 0 ? "+" : ""}{record.sellAvg.toFixed(1)}% on average, where down is right. </>}
                Only calls at least three days old count, and a few calls prove little. This is not advice.
              </div>
            </div>
          )}

          <div className="history-tools">
            <div className="committee-tabs" role="tablist" aria-label="Filter by verdict">
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  role="tab"
                  aria-selected={filter === f.id}
                  className={`committee-tab${filter === f.id ? " committee-tab--active" : ""}`}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <input
              type="search"
              className="history-search"
              placeholder="Find a ticker"
              aria-label="Find a ticker"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {shown.length === 0 ? (
            <div className="card" style={{ textAlign: "center", color: "var(--text-dim)", padding: "34px 20px" }}>
              No saved debate matches that.
            </div>
          ) : (
            <div className="history-list">
              {shown.map((entry) => (
                <HistoryCard key={entry.id} entry={entry} onDelete={onDelete} move={sinceCall(entry, prices)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
