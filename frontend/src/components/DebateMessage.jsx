import { useState } from "react";
import { AGENT_META, AGENT_ORDER, agentColor, splitMentions } from "../agentMeta.js";
import { crossExam } from "../api.js";
import AgentAvatar from "./AgentAvatar.jsx";
import BioAvatar from "./BioAvatar.jsx";

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

export default function DebateMessage({
  ticker,
  turn,
  agentKey,
  text,
  allowCrossExam = true,
  initialExams = [],
  onExamsChange,
  agents = AGENT_ORDER,
}) {
  const [examOpen, setExamOpen] = useState(false);
  const [examiner, setExaminer] = useState(
    agents.find((k) => k !== agentKey) || agents[0]
  );
  const [exams, setExams] = useState(initialExams);
  const [asking, setAsking] = useState(false);

  const meta = AGENT_META[agentKey];
  const color = agentColor(agentKey);

  async function handleAsk() {
    setAsking(true);
    try {
      const res = await crossExam(ticker, examiner, agentKey, text);
      const next = [...exams, res];
      setExams(next);
      onExamsChange?.(turn, next);
      setExamOpen(false);
    } catch (err) {
      const next = [...exams, { agent: examiner, text: `(cross-exam failed: ${err.message})` }];
      setExams(next);
      onExamsChange?.(turn, next);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="fade-in" style={{ display: "flex", gap: 12, marginBottom: 18 }}>
      <BioAvatar agentKey={agentKey} size="md" style={{ marginTop: 2 }} />
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
          <span style={{ color, fontWeight: 600 }}>{meta.name}</span>
          <span style={{ color: "var(--text-faint)", fontSize: "0.75rem" }}>turn {turn}</span>
        </div>
        <div style={{ fontSize: "0.95rem", lineHeight: 1.55 }}>
          <Highlighted text={text} />
        </div>

        {allowCrossExam && (
          <button
            onClick={() => setExamOpen((o) => !o)}
            className="button-secondary cross-exam-toggle"
            style={{ marginTop: 8, fontSize: "0.75rem" }}
          >
            Cross-examine
          </button>
        )}

        {allowCrossExam && examOpen && (
          <div className="exam-picker fade-in">
            <div className="ask-audience-label">
              Who should question <strong>{meta.name}</strong>?{" "}
              <strong style={{ color: agentColor(examiner) }}>{AGENT_META[examiner]?.name}</strong>
            </div>
            <div className="exam-row">
              <div className="ask-audience" role="radiogroup" aria-label="Who should cross-examine?">
                {agents
                  .filter((k) => k !== agentKey)
                  .map((k) => (
                    <button
                      key={k}
                      type="button"
                      role="radio"
                      aria-checked={examiner === k}
                      aria-label={AGENT_META[k]?.name}
                      title={AGENT_META[k]?.name}
                      className={`ask-seat${examiner === k ? " ask-seat--on" : ""}`}
                      style={{ "--seat-color": agentColor(k) }}
                      onClick={() => setExaminer(k)}
                    >
                      <AgentAvatar agentKey={k} size="fill" />
                    </button>
                  ))}
              </div>
              <button className="button-secondary" disabled={asking} onClick={handleAsk}>
                {asking ? "Asking…" : "Ask"}
              </button>
            </div>
          </div>
        )}

        {exams.map((exam, i) => (
          <div
            key={i}
            className="fade-in"
            style={{
              display: "flex",
              gap: 10,
              marginTop: 10,
              paddingLeft: 14,
              borderLeft: `2px dashed ${agentColor(exam.agent)}`,
            }}
          >
            <AgentAvatar agentKey={exam.agent} size="sm" style={{ marginTop: 2 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-faint)", marginBottom: 2 }}>
                Cross-examined by {AGENT_META[exam.agent]?.name ?? exam.agent}
              </div>
              <div style={{ fontSize: "0.9rem", fontStyle: "italic", color: "var(--text-dim)" }}>
                <Highlighted text={exam.text} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
