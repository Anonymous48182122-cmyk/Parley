import { useState } from "react";
import { AGENT_META, agentColor } from "../agentMeta.js";
import FormattedText from "./FormattedText.jsx";

export default function AgentCard({ agentKey, text }) {
  const [open, setOpen] = useState(false);
  const meta = AGENT_META[agentKey];
  const color = agentColor(agentKey);

  return (
    <div
      className="card fade-in"
      style={{ borderLeft: `3px solid ${color}`, borderRadius: "4px 22px 22px 4px" }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          all: "unset",
          display: "flex",
          alignItems: "center",
          gap: 12,
          width: "100%",
          cursor: "pointer",
        }}
      >
        <span className="monogram" style={{ background: color }}>
          {meta.monogram}
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{meta.name}</div>
          <div style={{ color: "var(--text-dim)", fontSize: "0.82rem" }}>{meta.role}</div>
        </div>
        <span style={{ color: "var(--text-faint)" }}>{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div style={{ marginTop: 16, fontSize: "0.92rem", lineHeight: 1.55 }}>
          <FormattedText text={text} accentColor={color} />
        </div>
      )}
    </div>
  );
}
