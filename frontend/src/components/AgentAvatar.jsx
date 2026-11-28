import { AGENT_META, agentColor } from "../agentMeta.js";
import { portraitOf, symbolOf } from "../floor.js";

// A member's face. Real people (investors and founders) have an engraved portrait (frontend/public/avatars).
// The members who are not people (the Historian, the Future Agent, the two advocates and the CIO) have a mark of
// their own, drawn in type, so they look the same on the floor, in the debate and everywhere else.
export default function AgentAvatar({ agentKey, size = "md", style }) {
  const meta = agentKey ? AGENT_META[agentKey] : null;
  // Guard against an unknown or missing key (the "whole committee" pending state): agentColor() would otherwise
  // emit var(--agent-null), an undefined property that breaks the fallback chain.
  const color = meta ? agentColor(agentKey) : "var(--accent)";
  const portrait = agentKey ? portraitOf(agentKey) : null;

  return (
    <span className={`agent-avatar agent-avatar--${size}`} style={{ "--avatar-color": color, ...style }} title={meta?.name}>
      {portrait ? (
        <img className="agent-avatar-portrait" src={portrait} alt={meta?.name ?? agentKey} />
      ) : (
        <span className="agent-avatar-symbol" aria-hidden="true">
          {agentKey ? symbolOf(agentKey) : "¶"}
        </span>
      )}
    </span>
  );
}
