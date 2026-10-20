import { AGENT_META } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";

const SHORT = { dhirubhai: "Dhirubhai", jhunjhunwala: "Rakesh" };

function shortName(key) {
  if (SHORT[key]) return SHORT[key];
  const name = AGENT_META[key]?.name ?? key;
  if (name.startsWith("The ")) return name.slice(4);
  return name.split(" ").pop();
}

// Everyone in the room along the top of the debate: the person speaking right now glows and
// pulses, and a small count shows how many times each has spoken. It sticks under the nav
// while the debate scrolls by, so you always know who is talking and who is waiting.
export default function SpeakerRail({ agents, debate = [], speaking }) {
  if (!agents || agents.length === 0) return null;
  const spoken = {};
  debate.forEach((t) => {
    spoken[t.agent] = (spoken[t.agent] || 0) + 1;
  });

  return (
    <div className="rail" role="list" aria-label="Committee members">
      {agents.map((k) => (
        <div
          key={k}
          role="listitem"
          className={`rail-seat${speaking === k ? " rail-seat--speaking" : ""}${spoken[k] ? " rail-seat--spoke" : ""}`}
          style={{ "--rail-color": `var(--agent-${k})` }}
          title={AGENT_META[k]?.name}
        >
          <span className="rail-avatar">
            <AgentAvatar agentKey={k} size="md" />
            {spoken[k] > 0 && <span className="rail-count">{spoken[k]}</span>}
          </span>
          <span className="rail-name">{shortName(k)}</span>
          {speaking === k && <span className="rail-live">speaking</span>}
        </div>
      ))}
    </div>
  );
}
