import { useEffect, useState } from "react";
import { AGENT_META, AGENT_ORDER, agentColor, splitMentions } from "../agentMeta.js";
import { askCommittee } from "../api.js";

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

function AnswerBubble({ response }) {
  const meta = AGENT_META[response.agent];
  const color = agentColor(response.agent);
  return (
    <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
      <span className="monogram" style={{ background: color, marginTop: 2, flexShrink: 0 }}>
        {meta?.monogram ?? "?"}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ color, fontWeight: 600, fontSize: "0.9rem" }}>{meta?.name ?? response.agent}</span>
        <div style={{ fontSize: "0.92rem", lineHeight: 1.55, marginTop: 2 }}>
          <Highlighted text={response.text} />
        </div>
      </div>
    </div>
  );
}

function PendingBubble({ agentKey }) {
  const meta = agentKey ? AGENT_META[agentKey] : null;
  return (
    <div className="fade-in" style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, color: "var(--text-dim)" }}>
      <span className="monogram" style={{ background: agentKey ? agentColor(agentKey) : "var(--gold)", opacity: 0.7, flexShrink: 0 }}>
        {meta?.monogram ?? "…"}
      </span>
      <span style={{ fontSize: "0.9rem" }}>{meta ? `${meta.name} is thinking` : "The whole committee is weighing in"}</span>
      <span className="typing-dots">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

export default function ChatPanel({ ticker, initialChat, ready }) {
  const [chat, setChat] = useState(initialChat || []);
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [pendingTarget, setPendingTarget] = useState("all");
  const [target, setTarget] = useState("all");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  // Seed once per ticker from whatever the job already had persisted
  // (e.g. after a page refresh) — chat state is then owned locally so it
  // doesn't fight with the debate poll loop re-fetching the same job.
  useEffect(() => {
    setChat(initialChat && initialChat.length ? initialChat : []);
    setError(null);
  }, [ticker]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAsk(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || sending) return;
    setSending(true);
    setError(null);
    setPendingQuestion(q);
    setPendingTarget(target);
    setQuestion("");
    try {
      const entry = await askCommittee(ticker, q, target === "all" ? null : target);
      setChat((prev) => [...prev, entry]);
    } catch (err) {
      setError(err.message);
      setQuestion(q);
    } finally {
      setSending(false);
    }
  }

  return (
    <section style={{ marginBottom: 40 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 16 }}>
        <h2
          style={{
            fontSize: "0.8rem",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-faint)",
          }}
        >
          Join the Debate
        </h2>
        <span style={{ fontSize: "0.78rem", color: "var(--text-faint)" }}>
          Ask the committee anything about {ticker.toUpperCase()}
        </span>
      </div>

      <div className="card">
        {chat.length === 0 && !sending && (
          <div style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>
            Have a doubt about the thesis? Ask a specific member or put it to the whole
            committee — you'll get a real, in-character answer grounded in this debate.
          </div>
        )}

        {chat.map((entry, i) => (
          <div key={i} style={{ marginBottom: i === chat.length - 1 ? 0 : 22 }}>
            <div
              className="fade-in"
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
            {entry.responses.map((r, j) => (
              <AnswerBubble key={j} response={r} />
            ))}
          </div>
        ))}

        {sending && (
          <div style={{ marginTop: chat.length ? 22 : 0 }}>
            <div
              className="fade-in"
              style={{
                background: "var(--gold-soft)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: "10px 14px",
                fontSize: "0.92rem",
              }}
            >
              <span style={{ color: "var(--gold)", fontWeight: 600, marginRight: 8 }}>You</span>
              {pendingQuestion}
            </div>
            {pendingTarget === "all" ? (
              <PendingBubble agentKey={null} />
            ) : (
              <PendingBubble agentKey={pendingTarget} />
            )}
          </div>
        )}

        <form onSubmit={handleAsk} style={{ display: "flex", gap: 8, marginTop: chat.length || sending ? 20 : 16 }}>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={!ready || sending}
            style={{
              background: "var(--surface-raised)",
              color: "var(--text)",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--radius-sm)",
              padding: "0 10px",
              fontSize: "0.85rem",
              flexShrink: 0,
              maxWidth: 150,
            }}
          >
            <option value="all">Whole committee</option>
            {AGENT_ORDER.map((k) => (
              <option key={k} value={k}>
                {AGENT_META[k].name}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder={ready ? "Ask a question or raise a doubt…" : "Waiting on the committee to convene…"}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!ready || sending}
            style={{ flex: 1 }}
          />
          <button type="submit" className="button-primary" disabled={!ready || sending || !question.trim()}>
            {sending ? "Asking…" : "Ask"}
          </button>
        </form>

        {error && (
          <div style={{ color: "var(--danger)", fontSize: "0.85rem", marginTop: 10 }}>{error}</div>
        )}
      </div>
    </section>
  );
}
