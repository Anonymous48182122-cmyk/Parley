import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { getHistoryEntry } from "../api.js";
import { AGENT_ORDER } from "../agentMeta.js";
import AgentCard from "./AgentCard.jsx";
import DebateMessage from "./DebateMessage.jsx";
import CIOMemo from "./CIOMemo.jsx";
import SectionLabel from "./SectionLabel.jsx";

export default function ReplayPage() {
  const { id } = useParams();
  const { session } = useAuth();
  const [entry, setEntry] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!session) return;
    getHistoryEntry(session.access_token, id)
      .then(setEntry)
      .catch((err) => setError(err.message));
  }, [session, id]);

  if (error) {
    return (
      <div className="container">
        <div style={{ color: "var(--danger)" }}>{error}</div>
      </div>
    );
  }
  if (!entry) {
    return (
      <div className="container">
        <div style={{ color: "var(--text-dim)" }}>Loading…</div>
      </div>
    );
  }

  return (
    <div className="container">
      <Link to="/history" style={{ color: "var(--text-faint)", fontSize: "0.85rem" }}>
        ← back to history
      </Link>

      <div style={{ display: "flex", alignItems: "baseline", gap: 12, margin: "16px 0 28px" }}>
        <h1 className="ticker" style={{ fontSize: "2rem" }}>
          {entry.ticker}
        </h1>
        {entry.market && <span className="pill">{entry.market}</span>}
        <span style={{ color: "var(--text-faint)", fontSize: "0.85rem" }}>
          Saved {new Date(entry.created_at).toLocaleString()}
        </span>
      </div>

      {Object.keys(entry.stage1 || {}).length > 0 && (
        <section style={{ marginBottom: 40 }}>
          <SectionLabel>Independent First Pass</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {AGENT_ORDER.filter((key) => entry.stage1[key]).map((key) => (
              <AgentCard key={key} agentKey={key} text={entry.stage1[key]} />
            ))}
          </div>
        </section>
      )}

      {(entry.debate || []).length > 0 && (
        <section style={{ marginBottom: 40 }}>
          <SectionLabel>Live Debate</SectionLabel>
          <div className="card">
            {entry.debate.map((turn) => (
              <DebateMessage
                key={turn.turn}
                ticker={entry.ticker}
                turn={turn.turn}
                agentKey={turn.agent}
                text={turn.text}
                allowCrossExam={false}
              />
            ))}
          </div>
        </section>
      )}

      {entry.cio_memo && (
        <section>
          <CIOMemo text={entry.cio_memo} />
        </section>
      )}
    </div>
  );
}
