import { AGENT_META, AGENT_ORDER, MIN_AGENTS } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";

// Shared by SearchPage (to build the roster before starting) — a plain
// checkbox grid grouped into the two AGENT_META "kind"s, since mixing real
// investors and the fictional framework roles in one undifferentiated list
// would blur what's actually being picked.
function Group({ title, keys, selected, onToggle }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <h3
        style={{
          fontSize: "0.78rem",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--text-faint)",
          marginBottom: 12,
        }}
      >
        {title}
      </h3>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 10,
        }}
      >
        {keys.map((key) => {
          const checked = selected.has(key);
          const meta = AGENT_META[key];
          return (
            <button
              key={key}
              type="button"
              onClick={() => onToggle(key)}
              className="card card-interactive"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "12px 14px",
                textAlign: "left",
                borderColor: checked ? "var(--gold)" : undefined,
                opacity: checked ? 1 : 0.55,
              }}
            >
              <AgentAvatar agentKey={key} size="md" />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{meta.name}</div>
                <div style={{ color: "var(--text-dim)", fontSize: "0.76rem" }}>{meta.role}</div>
              </div>
              <div
                aria-hidden="true"
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 5,
                  flexShrink: 0,
                  border: `1.5px solid ${checked ? "var(--gold)" : "var(--border-strong)"}`,
                  background: checked ? "var(--gold)" : "transparent",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "0.7rem",
                  color: "var(--bg)",
                }}
              >
                {checked ? "✓" : ""}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function CommitteePicker({ selected, onChange, onReset, defaultAgents }) {
  const investors = AGENT_ORDER.filter((k) => AGENT_META[k].kind === "investor");
  const special = AGENT_ORDER.filter((k) => AGENT_META[k].kind === "special");

  function toggle(key) {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  const isDefault =
    selected.size === defaultAgents.length && defaultAgents.every((k) => selected.has(k));

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 18,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <h2
          style={{
            fontSize: "0.8rem",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-faint)",
          }}
        >
          Build Your Committee
        </h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: "0.78rem", color: "var(--text-faint)" }}>
            {selected.size} selected
            {selected.size < MIN_AGENTS ? ` — pick at least ${MIN_AGENTS}` : ""}
          </span>
          {!isDefault && (
            <button
              type="button"
              className="button-secondary"
              style={{ fontSize: "0.75rem", padding: "4px 10px" }}
              onClick={onReset}
            >
              Reset to default
            </button>
          )}
        </div>
      </div>

      <Group title="Real Investors" keys={investors} selected={selected} onToggle={toggle} />
      <Group title="Special Roles" keys={special} selected={selected} onToggle={toggle} />
    </div>
  );
}
