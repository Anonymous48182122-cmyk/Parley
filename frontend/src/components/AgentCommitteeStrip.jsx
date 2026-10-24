import { useState } from "react";
import { AGENT_ORDER, AGENT_META, agentColor } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";
import BioAvatar from "./BioAvatar.jsx";
import FormattedText from "./FormattedText.jsx";
import VoteBoard from "./VoteBoard.jsx";
import { finalStances } from "../stance.js";

// Collapses Stage 1's 9 independent write-ups into one compact chip row —
// shared by the live CommitteePage and the read-only ReplayPage so both
// render Stage 1 identically instead of diverging.
export default function AgentCommitteeStrip({ stage1, debate, total }) {
  const [expanded, setExpanded] = useState(null);
  const available = AGENT_ORDER.filter((key) => stage1[key]);
  const stances = finalStances(stage1, debate);
  const debated = (debate || []).length > 0;

  if (available.length === 0) return null;

  return (
    <div>
      <VoteBoard stances={stances} debated={debated} total={total} />
      <div className="committee-strip">
        {available.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setExpanded((cur) => (cur === key ? null : key))}
            className={
              expanded === key ? "committee-chip committee-chip--active" : "committee-chip"
            }
          >
            <BioAvatar agentKey={key} size="sm" />
            <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>{AGENT_META[key].name}</span>
            <span className="chip-stance" style={{ color: stances[key].final.color }}>
              {stances[key].final.label}
            </span>
            {stances[key].changed && (
              <span className="chip-was" title={`First call was ${stances[key].opening.label}`}>
                was {stances[key].opening.label}
              </span>
            )}
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
            <BioAvatar agentKey={expanded} size="md" />
            <div>
              <div style={{ fontWeight: 600 }}>{AGENT_META[expanded].name}</div>
              <div style={{ color: "var(--text-dim)", fontSize: "0.82rem" }}>
                {AGENT_META[expanded].role}
              </div>
            </div>
          </div>
          {stances[expanded]?.changed && (
            <div className="stance-note">
              First call: <b style={{ color: stances[expanded].opening.color }}>{stances[expanded].opening.label}</b>. After the
              debate: <b style={{ color: stances[expanded].final.color }}>{stances[expanded].final.label}</b>. The write up
              below is the first call, before the debate.
            </div>
          )}
          <div style={{ fontSize: "0.92rem", lineHeight: 1.55 }}>
            <FormattedText text={stage1[expanded]} accentColor={agentColor(expanded)} />
          </div>
        </div>
      )}
    </div>
  );
}
