import AgentAvatar from "./AgentAvatar.jsx";
import FormattedText from "./FormattedText.jsx";

export default function CIOMemo({ text }) {
  return (
    <div className="card-gold fade-in">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
        <AgentAvatar agentKey="cio" size="md" />
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
