import { useState } from "react";
import { AGENT_META, AGENT_ORDER, LARGE_COMMITTEE, MIN_AGENTS, PRESETS, agentColor } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";
import AgentBioModal from "./AgentBioModal.jsx";

// Choosing who sits on the committee. The ready made committees come first, each answering a question a reader
// actually has; "Choose members yourself" opens the full list for anyone who wants to.

const GROUPS = [
  { kind: "investor", label: "Investors" },
  { kind: "legend", label: "Founders and legends" },
  { kind: "special", label: "Special roles" },
];

function roundsFor(n) {
  if (n <= 4) return 3;
  if (n <= 6) return 2;
  return 1;
}

function sameSet(selected, keys) {
  return selected.size === keys.length && keys.every((k) => selected.has(k));
}

function Faces({ keys, max = 6 }) {
  return (
    <span className="faces">
      {keys.slice(0, max).map((k) => (
        <AgentAvatar key={k} agentKey={k} size="sm" />
      ))}
      {keys.length > max && <em>+{keys.length - max}</em>}
    </span>
  );
}

export default function CommitteeRoster({ selected, onChange }) {
  const active = PRESETS.find((p) => sameSet(selected, p.keys));
  const [custom, setCustom] = useState(() => !active);
  const [bio, setBio] = useState(null);
  const n = selected.size;
  const tooFew = n < MIN_AGENTS;

  function toggle(key) {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  return (
    <section className="roster" aria-label="Your committee">
      <header className="sec-head">
        <h2>Your committee</h2>
        <p className={tooFew ? "warn" : ""}>
          {tooFew
            ? `Choose at least ${MIN_AGENTS} members.`
            : `${n} members, ${n * roundsFor(n)} debate turns.${n > LARGE_COMMITTEE ? " Six to ten debate sharpest." : ""}`}
        </p>
      </header>

      <div className="preset-list" role="radiogroup" aria-label="Ready made committees">
        {PRESETS.map((p) => {
          const on = active?.id === p.id;
          return (
            <button key={p.id} type="button" role="radio" aria-checked={on} className={`preset${on ? " preset--on" : ""}`} onClick={() => onChange(new Set(p.keys))}>
              <span className="preset-name">
                {p.label}
                <em>{p.keys.length}</em>
              </span>
              <span className="preset-blurb-line">{p.blurb}</span>
              <Faces keys={p.keys} />
            </button>
          );
        })}
      </div>

      <button type="button" className="disclose" aria-expanded={custom} onClick={() => setCustom((v) => !v)}>
        <span>{custom ? "Hide the member list" : "Choose members yourself"}</span>
        <i aria-hidden="true" />
      </button>

      {custom && (
        <div className="members">
          {GROUPS.map((g) => {
            const keys = AGENT_ORDER.filter((k) => AGENT_META[k].kind === g.kind);
            return (
              <fieldset key={g.kind}>
                <legend>{g.label}</legend>
                {keys.map((k) => {
                  const on = selected.has(k);
                  return (
                    <div key={k} className={`member${on ? " member--on" : ""}`} style={{ "--member": agentColor(k) }}>
                      <label>
                        <input type="checkbox" checked={on} onChange={() => toggle(k)} />
                        <AgentAvatar agentKey={k} size="sm" />
                        <span>
                          <b>{AGENT_META[k].name}</b>
                          <em>{AGENT_META[k].role}</em>
                        </span>
                      </label>
                      <button type="button" className="member-bio" onClick={() => setBio(k)}>
                        How they think
                      </button>
                    </div>
                  );
                })}
              </fieldset>
            );
          })}
          <p className="roster-note">
            Founders and legends are builders, not stock pickers. They are AI interpretations of how they thought and
            built, not their actual views.
          </p>
        </div>
      )}

      <AgentBioModal agentKey={bio} onClose={() => setBio(null)} />
    </section>
  );
}
