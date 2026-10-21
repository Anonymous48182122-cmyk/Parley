import { useEffect, useRef, useState } from "react";
import { AGENT_META, AGENT_ORDER, agentColor, splitMentions } from "../agentMeta.js";
import { askCommittee } from "../api.js";
import AgentAvatar from "./AgentAvatar.jsx";
import BioAvatar from "./BioAvatar.jsx";

// Starting points, for the person who is not sure what to ask. They fit any stock.
const STARTERS = [
  "What would change your mind?",
  "What is the biggest risk here?",
  "Is it cheap or expensive at this price?",
  "What is the market missing?",
  "Would you buy more if it fell 20 percent?",
];

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

function YouBubble({ text }) {
  return (
    <div className="ask-you fade-in">
      <span>{text}</span>
    </div>
  );
}

function AnswerBubble({ response }) {
  const meta = AGENT_META[response.agent];
  return (
    <div className="ask-answer fade-in" style={{ "--answer-color": agentColor(response.agent) }}>
      <BioAvatar agentKey={response.agent} size="md" style={{ marginTop: 2 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="ask-answer-name">{meta?.name ?? response.agent}</div>
        <div className="ask-answer-text">
          <Highlighted text={response.text} />
        </div>
      </div>
    </div>
  );
}

function PendingBubble({ agentKey }) {
  const meta = agentKey ? AGENT_META[agentKey] : null;
  return (
    <div className="fade-in ask-pending">
      <AgentAvatar agentKey={agentKey} size="md" style={{ opacity: 0.75 }} />
      <span>{meta ? `${meta.name} is thinking` : "The whole committee is weighing in"}</span>
      <span className="typing-dots">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

// Who to ask: the whole room, or one person, chosen by tapping their portrait.
function Audience({ agents, target, onChange, disabled }) {
  return (
    <div className="ask-audience" role="radiogroup" aria-label="Who do you want to ask?">
      <button
        type="button"
        role="radio"
        aria-checked={target === "all"}
        disabled={disabled}
        className={`ask-all${target === "all" ? " ask-all--on" : ""}`}
        onClick={() => onChange("all")}
      >
        Everyone
      </button>
      {agents.map((k) => (
        <button
          key={k}
          type="button"
          role="radio"
          aria-checked={target === k}
          aria-label={AGENT_META[k]?.name}
          title={AGENT_META[k]?.name}
          disabled={disabled}
          className={`ask-seat${target === k ? " ask-seat--on" : ""}`}
          style={{ "--seat-color": agentColor(k) }}
          onClick={() => onChange(k)}
        >
          <AgentAvatar agentKey={k} size="fill" />
        </button>
      ))}
    </div>
  );
}

export default function ChatPanel({ ticker, initialChat, ready, agents = AGENT_ORDER }) {
  const [chat, setChat] = useState(initialChat || []);
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [pendingTarget, setPendingTarget] = useState("all");
  const [target, setTarget] = useState("all");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  // Seed once per ticker from whatever the job already had persisted
  // (e.g. after a page refresh). Chat state is then owned locally so it
  // doesn't fight with the debate poll loop re-fetching the same job.
  useEffect(() => {
    setChat(initialChat && initialChat.length ? initialChat : []);
    setError(null);
  }, [ticker]); // eslint-disable-line react-hooks/exhaustive-deps

  async function ask(text) {
    const q = text.trim();
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

  function handleAsk(e) {
    e.preventDefault();
    ask(question);
  }

  const askingName = target === "all" ? "the whole committee" : AGENT_META[target]?.name;
  const disabled = !ready || sending;

  return (
    <section className="ask">
      <div className="ask-head">
        <h2>Join the debate</h2>
        <span>Ask the committee anything about {ticker.toUpperCase()}</span>
      </div>

      <div className="card ask-card">
        {chat.length === 0 && !sending && (
          <div className="ask-intro">
            Have a doubt about the thesis? Ask one member or put it to the whole committee. You get a real,
            in character answer based on this debate.
          </div>
        )}

        {chat.map((entry, i) => (
          <div key={i} className="ask-entry">
            <YouBubble text={entry.question} />
            {entry.responses.map((r, j) => (
              <AnswerBubble key={j} response={r} />
            ))}
          </div>
        ))}

        {sending && (
          <div className="ask-entry">
            <YouBubble text={pendingQuestion} />
            <PendingBubble agentKey={pendingTarget === "all" ? null : pendingTarget} />
          </div>
        )}

        <div className="ask-composer-wrap">
          <div className="ask-audience-label">
            Asking <strong>{askingName}</strong>
          </div>
          <Audience agents={agents} target={target} onChange={setTarget} disabled={disabled} />

          {!sending && ready && (
            <div className="ask-starters" aria-label="Question ideas">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="ask-starter"
                  onClick={() => {
                    setQuestion(s);
                    inputRef.current?.focus();
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={handleAsk} className="ask-form">
            <input
              ref={inputRef}
              type="text"
              placeholder={ready ? "Ask a question or raise a doubt" : "Waiting on the committee to convene"}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={disabled}
              aria-label="Your question"
            />
            <button type="submit" className="button-primary" disabled={disabled || !question.trim()}>
              {sending ? "Asking…" : "Ask"}
            </button>
          </form>

          {error && <div className="ask-error">{error}</div>}
        </div>
      </div>
    </section>
  );
}
