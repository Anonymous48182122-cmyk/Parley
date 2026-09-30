import { useState } from "react";
import AgentAvatar from "./AgentAvatar.jsx";
import FormattedText from "./FormattedText.jsx";
import VerdictBadge from "./VerdictBadge.jsx";

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard access can be denied (permissions, insecure context) —
      // failing silently is fine, the button just won't show "Copied ✓"
    }
  }

  return (
    <button
      type="button"
      className="button-secondary"
      onClick={handleCopy}
      style={{ fontSize: "0.75rem", padding: "5px 12px", flexShrink: 0 }}
    >
      {copied ? "Copied ✓" : "Copy memo"}
    </button>
  );
}

export default function CIOMemo({ text, verdict, conviction }) {
  return (
    <div className="card-gold fade-in">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 18,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <AgentAvatar agentKey="cio" size="md" />
          <div>
            <h2 style={{ fontSize: "1.3rem" }}>CIO Memo</h2>
            <div style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
              Synthesis — not a vote, a map of where the committee actually landed
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <VerdictBadge verdict={verdict} conviction={conviction} />
          <CopyButton text={text} />
        </div>
      </div>
      <div style={{ fontSize: "0.95rem", lineHeight: 1.6 }}>
        <FormattedText text={text} accentColor="var(--gold)" />
      </div>
    </div>
  );
}
