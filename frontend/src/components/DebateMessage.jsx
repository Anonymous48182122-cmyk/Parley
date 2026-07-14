import { useState } from "react";
import { AGENT_META, AGENT_ORDER, agentColor, splitMentions } from "../agentMeta.js";
import { crossExam } from "../api.js";

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

export default function DebateMessage({ ticker, turn, agentKey, text, allowCrossExam = true }) {
  const [examOpen, setExamOpen] = useState(false);
  const [examiner, setExaminer] = useState(
    AGENT_ORDER.find((k) => k !== agentKey) || AGENT_ORDER[0]
  );
  const [exams, setExams] = useState([]);
  const [asking, setAsking] = useState(false);

  const meta = AGENT_META[agentKey];
  const color = agentColor(agentKey);

  async function handleAsk() {
    setAsking(true);
    try {
      const res = await crossExam(ticker, examiner, agentKey, text);
      setExams((prev) => [...prev, res]);
      setExamOpen(false);
    } catch (err) {
      setExams((prev) => [...prev, { agent: examiner, text: `(cross-exam failed: ${err.message})` }]);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="fade-in" style={{ display: "flex", gap: 12, marginBottom: 18 }}>
      <span className="monogram" style={{ background: color, marginTop: 2 }}>
        {meta.monogram}
      </span>
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
            className="button-secondary"
            style={{ marginTop: 8, fontSize: "0.75rem", padding: "4px 10px" }}
          >
            Cross-examine
          </button>
        )}

        {allowCrossExam && examOpen && (
          <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
            <select
              value={examiner}
              onChange={(e) => setExaminer(e.target.value)}
              style={{
                background: "var(--surface-raised)",
                color: "var(--text)",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--radius-sm)",
                padding: "8px 10px",
                fontSize: "0.85rem",
              }}
            >
              {AGENT_ORDER.filter((k) => k !== agentKey).map((k) => (
                <option key={k} value={k}>
                  {AGENT_META[k].name}
                </option>
              ))}
            </select>
            <button className="button-secondary" disabled={asking} onClick={handleAsk}>
              {asking ? "Asking…" : "Ask"}
            </button>
          </div>
        )}

        {exams.map((exam, i) => (
          <div
            key={i}
            className="fade-in"
            style={{
              marginTop: 10,
              paddingLeft: 14,
              borderLeft: `2px dashed ${agentColor(exam.agent)}`,
            }}
          >
            <div style={{ fontSize: "0.7rem", color: "var(--text-faint)", marginBottom: 2 }}>
              CROSS-EXAM — {AGENT_META[exam.agent]?.name ?? exam.agent}
            </div>
            <div style={{ fontSize: "0.9rem", fontStyle: "italic", color: "var(--text-dim)" }}>
              <Highlighted text={exam.text} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
