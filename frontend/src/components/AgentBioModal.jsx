import { useEffect } from "react";
import { AGENT_META, agentColor } from "../agentMeta.js";
import { AGENT_BIOS } from "../agentBios.js";
import AgentAvatar from "./AgentAvatar.jsx";

// A deliberately quiet reveal — not a tooltip, not inline text everyone sees
// by default. Clicking an agent's portrait opens this; nothing about the
// chip itself advertises that there's more here, on purpose.
export default function AgentBioModal({ agentKey, onClose }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!agentKey) return null;
  const meta = AGENT_META[agentKey];
  const bio = AGENT_BIOS[agentKey];
  const color = agentColor(agentKey);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(2, 3, 7, 0.72)",
        backdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        zIndex: 200,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card fade-in"
        style={{
          maxWidth: 480,
          width: "100%",
          maxHeight: "85vh",
          overflowY: "auto",
          borderColor: color,
          position: "relative",
        }}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="button-secondary"
          style={{
            position: "absolute",
            top: 14,
            right: 14,
            padding: "4px 10px",
            fontSize: "0.8rem",
          }}
        >
          ✕
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <AgentAvatar agentKey={agentKey} size="lg" />
          <div>
            <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>{meta.name}</div>
            <div style={{ color, fontSize: "0.82rem", fontWeight: 600 }}>{meta.role}</div>
          </div>
        </div>

        <div style={{ fontSize: "0.95rem", lineHeight: 1.7, color: "var(--text-dim)" }}>
          {bio}
        </div>
      </div>
    </div>
  );
}
