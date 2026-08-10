import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AGENT_META, agentColor, splitMentions } from "../agentMeta.js";
import { useAuth } from "../AuthContext.jsx";
import { getHistoryEntry } from "../api.js";
import AgentAvatar from "./AgentAvatar.jsx";
import AgentCommitteeStrip from "./AgentCommitteeStrip.jsx";
import DebateMessage from "./DebateMessage.jsx";
import CIOMemo from "./CIOMemo.jsx";
import MarketSnapshot from "./MarketSnapshot.jsx";
import SectionLabel from "./SectionLabel.jsx";

function Highlighted({ text }) {
  return (
    <>
      {splitMentions(text).map((part, i) =>
        part.agentKey ? (
          <span key={i} style={{ color: agentColor(part.agentKey), fontWeight: 600 }}>
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </>
  );
}

function ChatReplay({ chat }) {
  if (!chat || chat.length === 0) return null;
  return (
    <section style={{ marginBottom: 40 }}>
      <SectionLabel>Join the Debate</SectionLabel>
      <div className="card">
        {chat.map((entry, i) => (
          <div key={i} style={{ marginBottom: i === chat.length - 1 ? 0 : 22 }}>
            <div
              style={{
                background: "var(--gold-soft)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: "10px 14px",
                fontSize: "0.92rem",
              }}
            >
              <span style={{ color: "var(--gold)", fontWeight: 600, marginRight: 8 }}>You</span>
              {entry.question}
            </div>
            {entry.responses.map((r, j) => {
              const meta = AGENT_META[r.agent];
              return (
                <div key={j} style={{ display: "flex", gap: 12, marginTop: 12 }}>
                  <AgentAvatar agentKey={r.agent} size="md" style={{ marginTop: 2 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ color: agentColor(r.agent), fontWeight: 600, fontSize: "0.9rem" }}>
                      {meta?.name ?? r.agent}
                    </span>
                    <div style={{ fontSize: "0.92rem", lineHeight: 1.55, marginTop: 2 }}>
                      <Highlighted text={r.text} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}

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

      <MarketSnapshot data={entry.market_data} />

      {Object.keys(entry.stage1 || {}).length > 0 && (
        <section style={{ marginBottom: 40 }}>
          <SectionLabel>Independent First Pass</SectionLabel>
          <AgentCommitteeStrip stage1={entry.stage1} />
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
                initialExams={(entry.cross_exams || {})[turn.turn] || []}
              />
            ))}
          </div>
        </section>
      )}

      <ChatReplay chat={entry.user_chat} />

      {entry.cio_memo && (
        <section>
          <CIOMemo text={entry.cio_memo} verdict={entry.verdict} conviction={entry.conviction} />
        </section>
      )}
    </div>
  );
}
