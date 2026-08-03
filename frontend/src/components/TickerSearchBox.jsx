import { useEffect, useRef, useState } from "react";
import { searchLocal } from "../popularTickers.js";
import { isTickerIndexReady, preloadTickerIndex, searchFullIndex } from "../tickerIndex.js";

const LIMIT = 8;

function mergeResults(local, full, limit) {
  const seen = new Set(full.map((r) => `${r.market}-${r.ticker}`));
  const extra = local.filter((r) => !seen.has(`${r.market}-${r.ticker}`));
  return [...full, ...extra].slice(0, limit);
}

export default function TickerSearchBox({ onSelect }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const [indexReady, setIndexReady] = useState(isTickerIndexReady());
  const blurTimeoutRef = useRef(null);

  useEffect(() => {
    preloadTickerIndex().then(() => setIndexReady(true));
  }, []);

  const trimmed = query.trim();
  // Entirely synchronous and zero-network: the curated ~90-ticker list
  // (popularTickers.js) covers the brief moment before the full ~12.8k-entry
  // index has finished its one-time fetch, and the full index covers
  // everything else once ready. No debounce, no backend round-trip per
  // keystroke — search speed no longer depends on Render's network/CPU
  // latency at all, which was the actual bottleneck users were hitting.
  const local = trimmed ? searchLocal(trimmed, LIMIT) : [];
  const full = trimmed && indexReady ? searchFullIndex(trimmed, LIMIT) : [];
  const results = mergeResults(local, full, LIMIT);

  useEffect(() => {
    setOpen(results.length > 0 && trimmed.length > 0);
    setHighlighted(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, indexReady]);

  function selectResult(result) {
    clearTimeout(blurTimeoutRef.current);
    setOpen(false);
    setQuery("");
    onSelect(result.ticker, result.market);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (open && results[highlighted]) {
      selectResult(results[highlighted]);
    } else if (query.trim()) {
      onSelect(query.trim().toUpperCase(), null);
      setQuery("");
      setOpen(false);
    }
  }

  function handleKeyDown(e) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => (h + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => (h - 1 + results.length) % results.length);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ position: "relative", marginBottom: 20 }}>
      <div className="search-row" style={{ display: "flex", gap: 10 }}>
        <input
          type="text"
          placeholder="Search by ticker or company — e.g. Apple, Reliance, PLTR"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setOpen(true)}
          onBlur={() => {
            blurTimeoutRef.current = setTimeout(() => setOpen(false), 150);
          }}
          autoFocus
          autoComplete="off"
        />
        <button type="submit" className="button-primary" style={{ whiteSpace: "nowrap" }}>
          Convene committee
        </button>
      </div>

      {open && results.length > 0 && (
        <div
          className="card fade-in search-dropdown"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
            right: 0,
            zIndex: 10,
            padding: 8,
            overflowY: "auto",
          }}
        >
          {results.map((result, i) => (
            <div
              key={`${result.market}-${result.ticker}`}
              onMouseDown={() => selectResult(result)}
              onMouseEnter={() => setHighlighted(i)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: "12px 14px",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                background: i === highlighted ? "var(--gold-soft)" : "transparent",
                transition: "background 0.15s var(--ease)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <span className="ticker" style={{ fontWeight: 600 }}>
                  {result.ticker}
                </span>
                <span
                  style={{
                    color: "var(--text-dim)",
                    marginLeft: 10,
                    fontSize: "0.88rem",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {result.name}
                </span>
              </div>
              <span className="pill" style={{ fontSize: "0.7rem", flexShrink: 0 }}>
                {result.market}
              </span>
            </div>
          ))}
        </div>
      )}
    </form>
  );
}
