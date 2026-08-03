import { useState } from "react";
import { AGENT_ORDER, AGENT_META, agentColor } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";
import FormattedText from "./FormattedText.jsx";

// Collapses Stage 1's 9 independent write-ups into one compact chip row —
// shared by the live CommitteePage and the read-only ReplayPage so both
// render Stage 1 identically instead of diverging.
export default function AgentCommitteeStrip({ stage1 }) {
  const [expanded, setExpanded] = useState(null);
  const available = AGENT_ORDER.filter((key) => stage1[key]);

  if (available.length === 0) return null;

  return (
    <div>
      <div className="committee-strip">
        {available.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setExpanded((cur) => (cur === key ? null : key))}
            title={`${AGENT_META[key].name} — ${AGENT_META[key].role}`}
            className={
              expanded === key ? "committee-chip committee-chip--active" : "committee-chip"
            }
          >
            <AgentAvatar agentKey={key} size="sm" />
          </button>
        ))}
      </div>

      {expanded && stage1[expanded] && (
        <div
          className="card fade-in"
          style={{
            marginTop: 14,
            borderLeft: `3px solid ${agentColor(expanded)}`,
            borderRadius: "4px 22px 22px 4px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <AgentAvatar agentKey={expanded} size="md" />
            <div>
              <div style={{ fontWeight: 600 }}>{AGENT_META[expanded].name}</div>
              <div style={{ color: "var(--text-dim)", fontSize: "0.82rem" }}>
                {AGENT_META[expanded].role}
              </div>
            </div>
          </div>
          <div style={{ fontSize: "0.92rem", lineHeight: 1.55 }}>
            <FormattedText text={stage1[expanded]} accentColor={agentColor(expanded)} />
          </div>
        </div>
      )}
    </div>
  );
}
