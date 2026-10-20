import { useMemo, useRef, useState } from "react";
import { AGENT_META, AGENT_ORDER, LARGE_COMMITTEE, MIN_AGENTS, PRESETS, agentColor } from "../agentMeta.js";
import { AGENT_BIOS } from "../agentBios.js";
import AgentAvatar from "./AgentAvatar.jsx";
import AgentBioModal from "./AgentBioModal.jsx";

// Mirrors agents/prompts.py's _rounds_for: smaller committees get more back and
// forth per agent, larger ones stay to one turn each.
function roundsFor(n) {
  if (n <= 4) return 3;
  if (n <= 6) return 2;
  return 1;
}

const GROUPS = [
  { kind: "investor", label: "Investors" },
  { kind: "legend", label: "Founders and Legends" },
  { kind: "special", label: "Special roles" },
];

// Seat order around the table: investors, then the founders, then the special roles,
// so each group sits together as an arc.
const SEATS = GROUPS.flatMap((g) => AGENT_ORDER.filter((k) => AGENT_META[k].kind === g.kind));

function sameSet(selected, keys) {
  return selected.size === keys.length && keys.every((k) => selected.has(k));
}

function firstSentence(text) {
  if (!text) return "";
  const end = text.indexOf(". ");
  return end === -1 ? text : text.slice(0, end + 1);
}

export default function CommitteePicker({ selected, onChange }) {
  const [focus, setFocus] = useState(null);
  const [bioAgent, setBioAgent] = useState(null);
  const stageRef = useRef(null);

  const n = selected.size;
  const turns = n * roundsFor(n);
  const activePreset = PRESETS.find((p) => sameSet(selected, p.keys));
  const tooFew = n < MIN_AGENTS;
  const tooMany = n > LARGE_COMMITTEE;

  // Seat positions on a circle, starting from the top and going clockwise.
  const seats = useMemo(
    () =>
      SEATS.map((key, i) => {
        const angle = ((-90 + (360 / SEATS.length) * i) * Math.PI) / 180;
        return { key, x: 50 + 41 * Math.cos(angle), y: 50 + 41 * Math.sin(angle) };
      }),
    []
  );

  function toggle(key) {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  function toggleGroup(kind) {
    const keys = SEATS.filter((k) => AGENT_META[k].kind === kind);
    const allOn = keys.every((k) => selected.has(k));
    const next = new Set(selected);
    keys.forEach((k) => (allOn ? next.delete(k) : next.add(k)));
    onChange(next);
  }

  const focusMeta = focus ? AGENT_META[focus] : null;
  const focusOn = focus ? selected.has(focus) : false;

  return (
    <section aria-label="Your committee" className="table-section">
      <div className="table-heading">
        <h2>The table</h2>
        <p>Tap a portrait to seat or dismiss them.</p>
      </div>

      <div
        className="table-stage"
        ref={stageRef}
        onMouseLeave={() => setFocus(null)}
      >
        <div className="table-surface" aria-hidden="true">
          <span className="table-ring table-ring--outer" />
          <span className="table-ring table-ring--inner" />
        </div>

        <div className="table-center" aria-live="polite">
          {focusMeta ? (
            <div className="table-focus fade-in" key={focus} style={{ "--focus-color": agentColor(focus) }}>
              <div className="table-focus-avatar">
                <AgentAvatar agentKey={focus} size="fill" />
              </div>
              <div className="table-focus-name">{focusMeta.name}</div>
              <div className="table-focus-role">{focusMeta.role}</div>
              <div className="table-focus-bio">{firstSentence(AGENT_BIOS[focus])}</div>
              <div className="table-focus-actions">
                <span className={`table-focus-state${focusOn ? " is-on" : ""}`}>
                  {focusOn ? "Seated" : "Not seated"}
                </span>
                <button type="button" className="link-button" onClick={() => setBioAgent(focus)}>
                  How they think
                </button>
              </div>
            </div>
          ) : (
            <div className="table-summary">
              <div className={`table-count${tooFew ? " is-warn" : ""}`}>{n}</div>
              <div className="table-count-label">{n === 1 ? "voice at the table" : "voices at the table"}</div>
              <div
                className="table-count-sub"
                style={{ color: tooFew ? "var(--danger)" : tooMany ? "var(--gold)" : undefined }}
              >
                {tooFew
                  ? `A debate needs at least ${MIN_AGENTS}`
                  : tooMany
                  ? `${turns} turns. Six to ten debates sharpest`
                  : `${turns} debate turns${activePreset ? ` · ${activePreset.label}` : ""}`}
              </div>
            </div>
          )}
        </div>

        {seats.map(({ key, x, y }) => {
          const on = selected.has(key);
          return (
            <button
              key={key}
              type="button"
              aria-pressed={on}
              aria-label={`${AGENT_META[key].name}, ${AGENT_META[key].role}. ${on ? "Seated" : "Not seated"}.`}
              className={`seat${on ? " seat--on" : ""}${focus === key ? " seat--focus" : ""}`}
              style={{ left: `${x}%`, top: `${y}%`, "--seat-color": agentColor(key) }}
              onClick={() => {
                toggle(key);
                setFocus(key);
              }}
              onMouseEnter={() => setFocus(key)}
              onFocus={() => setFocus(key)}
              onBlur={() => setFocus((cur) => (cur === key ? null : cur))}
            >
              <AgentAvatar agentKey={key} size="fill" />
            </button>
          );
        })}
      </div>

      <div className="table-groups" role="group" aria-label="Seat a whole group">
        {GROUPS.map((g) => {
          const keys = SEATS.filter((k) => AGENT_META[k].kind === g.kind);
          const on = keys.filter((k) => selected.has(k)).length;
          return (
            <button
              key={g.kind}
              type="button"
              className={`group-chip${on === keys.length ? " group-chip--all" : on > 0 ? " group-chip--some" : ""}`}
              onClick={() => toggleGroup(g.kind)}
            >
              <span className="group-chip-dot" />
              {g.label}
              <span className="group-chip-count">
                {on}/{keys.length}
              </span>
            </button>
          );
        })}
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

      <p className="table-note">
        Founders and legends are builders, not stock pickers. They are AI interpretations of how they
        thought and built, not their actual views.
      </p>

      <AgentBioModal agentKey={bioAgent} onClose={() => setBioAgent(null)} />
    </section>
  );
}
