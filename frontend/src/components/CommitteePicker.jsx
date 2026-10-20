import { useMemo, useState } from "react";
import { AGENT_META, AGENT_ORDER, LARGE_COMMITTEE, MIN_AGENTS, PRESETS } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";
import AgentBioModal from "./AgentBioModal.jsx";

// Mirrors agents/prompts.py's _rounds_for: smaller committees get more
// back and forth per agent, larger ones stay to one turn each. Shown so the
// size of a committee has a visible tradeoff before the debate starts.
function roundsFor(n) {
  if (n <= 4) return 3;
  if (n <= 6) return 2;
  return 1;
}

const TABS = [
  { id: "all", label: "All" },
  { id: "investor", label: "Investors" },
  { id: "legend", label: "Founders and Legends" },
  { id: "special", label: "Special roles" },
];

const LEGEND_NOTE =
  "Builders, not stock pickers. These are AI interpretations of how they thought and built, not their actual views.";

function sameSet(selected, keys) {
  return selected.size === keys.length && keys.every((k) => selected.has(k));
}

// A short row of overlapping portraits: the committee at a glance.
function AvatarStack({ keys, max = 7 }) {
  const shown = keys.slice(0, max);
  const extra = keys.length - shown.length;
  return (
    <div className="avatar-stack" aria-hidden="true">
      {shown.map((k) => (
        <span key={k} className="avatar-stack-item">
          <AgentAvatar agentKey={k} size="md" />
        </span>
      ))}
      {extra > 0 && <span className="avatar-stack-more">+{extra}</span>}
    </div>
  );
}

function AgentTile({ agentKey, checked, onToggle, onShowBio }) {
  const meta = AGENT_META[agentKey];
  return (
    <div
      role="checkbox"
      aria-checked={checked}
      tabIndex={0}
      onClick={() => onToggle(agentKey)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle(agentKey);
        }
      }}
      className={`agent-tile${checked ? " agent-tile--on" : ""}`}
    >
      {/* The portrait is its own target: a quiet "look closer" that does not
          fight the tile's select and deselect click. */}
      <span
        onClick={(e) => {
          e.stopPropagation();
          onShowBio(agentKey);
        }}
        title={`About ${meta.name}`}
        className="agent-tile-avatar"
      >
        <AgentAvatar agentKey={agentKey} size="md" />
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="agent-tile-name">{meta.name}</div>
        <div className="agent-tile-role">{meta.role}</div>
      </div>
      <span className="agent-tile-check" aria-hidden="true">
        {checked ? "✓" : ""}
      </span>
    </div>
  );
}

export default function CommitteePicker({ selected, onChange }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("all");
  const [query, setQuery] = useState("");
  const [bioAgent, setBioAgent] = useState(null);

  const chosen = useMemo(() => AGENT_ORDER.filter((k) => selected.has(k)), [selected]);
  const n = chosen.length;
  const turns = n * roundsFor(n);
  const activePreset = PRESETS.find((p) => sameSet(selected, p.keys));

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return AGENT_ORDER.filter((k) => {
      const meta = AGENT_META[k];
      if (meta.kind === "cio") return false;
      if (tab !== "all" && meta.kind !== tab) return false;
      return !q || meta.name.toLowerCase().includes(q) || meta.role.toLowerCase().includes(q);
    });
  }, [tab, query]);

  const countIn = (kind) => {
    const keys = AGENT_ORDER.filter((k) => kind === "all" || AGENT_META[k].kind === kind);
    return { on: keys.filter((k) => selected.has(k)).length, total: keys.length };
  };

  function toggle(key) {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  function setMany(keys, on) {
    const next = new Set(selected);
    keys.forEach((k) => (on ? next.add(k) : next.delete(k)));
    onChange(next);
  }

  const tooFew = n < MIN_AGENTS;
  const tooMany = n > LARGE_COMMITTEE;

  return (
    <section aria-label="Your committee">
      <div className="committee-summary">
        <AvatarStack keys={chosen} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="committee-summary-title">
            {tooFew ? "Pick at least 3 agents" : `${n} agents in your committee`}
          </div>
          <div
            className="committee-summary-sub"
            style={{ color: tooFew ? "var(--danger)" : tooMany ? "var(--gold)" : undefined }}
          >
            {tooFew
              ? `${n} selected. A debate needs at least ${MIN_AGENTS} voices.`
              : tooMany
              ? `${turns} debate turns. Big committees run long and thin out each voice. Six to ten gives the sharpest debate.`
              : `${turns} debate turns. ${activePreset ? `${activePreset.label} committee.` : "Custom committee."}`}
          </div>
        </div>
        <button
          type="button"
          className="button-secondary"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Done" : "Customize"}
        </button>
      </div>

      <div className="preset-row" role="group" aria-label="Committee presets">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`preset-pill${activePreset?.id === p.id ? " preset-pill--active" : ""}`}
            aria-pressed={activePreset?.id === p.id}
            onClick={() => onChange(new Set(p.keys))}
          >
            {p.label}
            <span className="preset-pill-count">{p.keys.length}</span>
          </button>
        ))}
      </div>

      {open && (
        <div className="committee-panel fade-in">
          <div className="committee-panel-top">
            <input
              type="search"
              className="committee-search"
              placeholder="Find an agent"
              aria-label="Find an agent"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="committee-tabs" role="tablist">
              {TABS.map((t) => {
                const c = countIn(t.id);
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    aria-selected={tab === t.id}
                    className={`committee-tab${tab === t.id ? " committee-tab--active" : ""}`}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                    <span className="committee-tab-count">
                      {c.on}/{c.total}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {tab === "legend" && <div className="committee-note">{LEGEND_NOTE}</div>}

          <div className="committee-panel-actions">
            <span>Tap a portrait to see how they think.</span>
            <span style={{ display: "flex", gap: 14 }}>
              <button type="button" className="link-button" onClick={() => setMany(visible, true)}>
                Select shown
              </button>
              <button type="button" className="link-button" onClick={() => setMany(visible, false)}>
                Clear shown
              </button>
            </span>
          </div>

          {visible.length === 0 ? (
            <div className="committee-empty">No agent matches "{query}".</div>
          ) : (
            <div className="agent-grid-scroll">
              <div className="agent-grid">
                {visible.map((key) => (
                  <AgentTile
                    key={key}
                    agentKey={key}
                    checked={selected.has(key)}
                    onToggle={toggle}
                    onShowBio={setBioAgent}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <AgentBioModal agentKey={bioAgent} onClose={() => setBioAgent(null)} />
    </section>
  );
}
