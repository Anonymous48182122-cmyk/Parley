import { useNavigate } from "react-router-dom";
import { AGENT_ORDER, AGENT_META } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";
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

export default function SearchPage() {
  const navigate = useNavigate();

  function goToTicker(value) {
    const clean = value.trim().toUpperCase();
    if (!clean) return;
    navigate(`/analysis/${encodeURIComponent(clean)}`);
  }

  return (
    <div className="container">
      <div style={{ textAlign: "center", marginTop: 32, marginBottom: 44 }}>
        <div className="pill" style={{ marginBottom: 24 }}>
          Nine frameworks · One live debate
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
          Pick a stock. Watch nine legendary investor frameworks argue about it in real
          time, then read a CIO memo that keeps the disagreement instead of averaging it
          away.
        </p>
      </div>

      <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
        <InstallAppButton />
      </div>

      <TickerSearchBox onSelect={(ticker) => goToTicker(ticker)} />

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 64, justifyContent: "center" }}>
        {QUICK_PICKS.map((pick) => (
          <button
            key={pick.ticker}
            className="button-secondary ticker"
            onClick={() => goToTicker(pick.ticker)}
          >
            {pick.ticker}
          </button>
        ))}
      </div>

      <h2
        style={{
          fontSize: "0.8rem",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--text-faint)",
          marginBottom: 18,
          textAlign: "center",
        }}
      >
        The Committee
      </h2>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "center" }}>
        {AGENT_ORDER.map((key, i) => (
          <div
            key={key}
            className="fade-in"
            title={`${AGENT_META[key].name} — ${AGENT_META[key].role}`}
            style={{ animationDelay: `${i * 0.04}s`, animationFillMode: "backwards" }}
          >
            <AgentAvatar agentKey={key} size="lg" />
          </div>
        ))}
      </div>
    </div>
  );
}
