import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DEFAULT_AGENTS, MIN_AGENTS } from "../agentMeta.js";
import CommitteePicker from "./CommitteePicker.jsx";
import InstallAppButton from "./InstallAppButton.jsx";
import TickerSearchBox from "./TickerSearchBox.jsx";

const QUICK_PICKS = [
  { ticker: "AAPL", market: "US" },
  { ticker: "NVDA", market: "US" },
  { ticker: "PLTR", market: "US" },
  { ticker: "RELIANCE", market: "India" },
  { ticker: "TCS", market: "India" },
  { ticker: "URBANCO", market: "India" },
];

const STORAGE_KEY = "parley.committee";

// The default committee before the Bull Advocate was added. The page saves the
// default to localStorage on first visit, so every returning visitor has this
// exact set stored; treat it as "never customised" and move them to the new
// default instead of freezing them on the old one. Any genuinely custom pick
// is left untouched.
const LEGACY_DEFAULT = [
  "buffett", "munger", "lynch", "jhunjhunwala", "simons",
  "ackman", "historian", "future", "devils_advocate",
];

function isLegacyDefault(keys) {
  return keys.length === LEGACY_DEFAULT.length && LEGACY_DEFAULT.every((k) => keys.includes(k));
}

function loadSavedCommittee() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set(DEFAULT_AGENTS);
    const keys = JSON.parse(raw);
    if (!Array.isArray(keys) || keys.length < MIN_AGENTS || isLegacyDefault(keys)) {
      return new Set(DEFAULT_AGENTS);
    }
    return new Set(keys);
  } catch {
    return new Set(DEFAULT_AGENTS);
  }
}

export default function SearchPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState(loadSavedCommittee);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...selected]));
    } catch {
      // best-effort convenience only — a blocked/private-mode storage write
      // just means the next visit falls back to the default committee
    }
  }, [selected]);

  function goToTicker(value) {
    const clean = value.trim().toUpperCase();
    if (!clean || selected.size < MIN_AGENTS) return;
    navigate(`/analysis/${encodeURIComponent(clean)}`, { state: { agents: [...selected] } });
  }

  return (
    <div className="container">
      <div style={{ textAlign: "center", marginTop: 32, marginBottom: 44 }}>
        <div className="pill" style={{ marginBottom: 24 }}>
          Your committee · One live debate
        </div>
        <h1 style={{ fontSize: "clamp(2rem, 9vw, 3.1rem)", marginBottom: 16, lineHeight: 1.05 }}>
          Parley
        </h1>
        <p
          style={{
            color: "var(--text-dim)",
            fontSize: "1.08rem",
            maxWidth: 480,
            margin: "0 auto",
            lineHeight: 1.6,
          }}
        >
          Pick a stock and pick your committee. Watch legendary investor frameworks argue
          about it in real time, then read a CIO memo that keeps the disagreement instead
          of averaging it away.
        </p>
      </div>

      <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
        <InstallAppButton />
      </div>

      <TickerSearchBox onSelect={(ticker) => goToTicker(ticker)} />

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 48, justifyContent: "center" }}>
        {QUICK_PICKS.map((pick) => (
          <button
            key={pick.ticker}
            className="button-secondary ticker"
            disabled={selected.size < MIN_AGENTS}
            onClick={() => goToTicker(pick.ticker)}
          >
            {pick.ticker}
          </button>
        ))}
      </div>

      <CommitteePicker
        selected={selected}
        onChange={setSelected}
        onReset={() => setSelected(new Set(DEFAULT_AGENTS))}
        defaultAgents={DEFAULT_AGENTS}
      />
    </div>
  );
}
