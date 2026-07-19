import { useEffect, useRef, useState } from "react";
import { searchTickers } from "../api.js";
import { searchLocal } from "../popularTickers.js";

const DEBOUNCE_MS = 150;

function mergeResults(local, backend, limit) {
  if (backend === null) return local; // backend hasn't responded yet — show local instantly
  const seen = new Set(backend.map((r) => `${r.market}-${r.ticker}`));
  const extra = local.filter((r) => !seen.has(`${r.market}-${r.ticker}`));
  return [...backend, ...extra].slice(0, limit);
}

const LIMIT = 8;

export default function TickerSearchBox({ onSelect }) {
  const [query, setQuery] = useState("");
  const [localResults, setLocalResults] = useState([]);
  const [backendResults, setBackendResults] = useState(null);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const debounceRef = useRef(null);
  const blurTimeoutRef = useRef(null);
  const requestIdRef = useRef(0);

  const results = mergeResults(localResults, backendResults, LIMIT);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    const trimmed = query.trim();
    requestIdRef.current += 1;
    const thisRequestId = requestIdRef.current;

    if (!trimmed) {
      setLocalResults([]);
      setBackendResults(null);
      setOpen(false);
      return;
    }

    // Instant, zero-latency local match — shows something on every keystroke
    // immediately, rather than a blank dropdown while the network call is
    // still in flight (which can take a while right after a cold start).
    const local = searchLocal(trimmed, LIMIT);
    setLocalResults(local);
    setBackendResults(null);
    setOpen(local.length > 0);
    setHighlighted(0);

    debounceRef.current = setTimeout(async () => {
      try {
        const matches = await searchTickers(trimmed);
        if (requestIdRef.current !== thisRequestId) return; // stale response, query changed since
        setBackendResults(matches);
        setOpen(matches.length > 0 || local.length > 0);
        setHighlighted(0);
      } catch {
        if (requestIdRef.current !== thisRequestId) return;
        // Backend search failed (or is still cold-starting) — keep showing
        // local results rather than clearing the dropdown to empty.
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(debounceRef.current);
  }, [query]);

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
      <div style={{ display: "flex", gap: 10 }}>
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
          className="card fade-in"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
            right: 0,
            zIndex: 10,
            padding: 8,
            maxHeight: 340,
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
