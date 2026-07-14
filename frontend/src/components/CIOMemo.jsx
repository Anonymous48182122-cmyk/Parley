import { AGENT_META } from "../agentMeta.js";
import FormattedText from "./FormattedText.jsx";

export default function CIOMemo({ text }) {
  return (
    <div className="card-gold fade-in">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
        <span className="monogram" style={{ background: "var(--agent-cio)" }}>
          {AGENT_META.cio.monogram}
        </span>
        <div>
          <h2 style={{ fontSize: "1.3rem" }}>CIO Memo</h2>
          <div style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
            Synthesis — not a vote, a map of where the committee actually landed
          </div>
        </div>
      </div>
      <div style={{ fontSize: "0.95rem", lineHeight: 1.6 }}>
        <FormattedText text={text} accentColor="var(--gold)" />
      </div>
    </div>
  );
}
