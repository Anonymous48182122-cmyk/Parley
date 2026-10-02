import { useState } from "react";
import { AGENT_BIOS } from "../agentBios.js";
import AgentAvatar from "./AgentAvatar.jsx";
import AgentBioModal from "./AgentBioModal.jsx";

// An avatar that opens that agent's character portrait when clicked. Used
// wherever a speaker's portrait appears mid-debate, so the curious can look
// closer without leaving the page. Agents with no bio (the CIO) render as a
// plain avatar. stopPropagation keeps a click here from also triggering a
// parent's own click handler (e.g. a chip that expands the first pass).
export default function BioAvatar({ agentKey, size = "md", style }) {
  const [open, setOpen] = useState(false);

  if (!agentKey || !AGENT_BIOS[agentKey]) {
    return <AgentAvatar agentKey={agentKey} size={size} style={style} />;
  }

  return (
    <>
      <span
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        style={{ cursor: "pointer", display: "inline-flex", flexShrink: 0 }}
      >
        <AgentAvatar agentKey={agentKey} size={size} style={style} />
      </span>
      {open && <AgentBioModal agentKey={agentKey} onClose={() => setOpen(false)} />}
    </>
  );
}
