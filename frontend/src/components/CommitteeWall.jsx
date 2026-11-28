import { useState } from "react";
import { AGENT_META, AGENT_ORDER, LARGE_COMMITTEE, MIN_AGENTS, PRESETS, shortName } from "../agentMeta.js";
import { Face } from "./Floor.jsx";
import AgentBioModal from "./AgentBioModal.jsx";

// Choosing the committee: every member as a portrait on one wall. Lit means seated. Ready made committees, each
// answering a question a reader actually has, sit above it.

function roundsFor(n) {
  if (n <= 4) return 3;
  if (n <= 6) return 2;
  return 1;
}

function sameSet(selected, keys) {
  return selected.size === keys.length && keys.every((k) => selected.has(k));
}

export default function CommitteeWall({ selected, onChange }) {
  const [bio, setBio] = useState(null);
  const [peek, setPeek] = useState(null);
  const active = PRESETS.find((p) => sameSet(selected, p.keys));
  const shown = PRESETS.find((p) => p.id === peek) || active;
  const n = selected.size;
  const tooFew = n < MIN_AGENTS;

  function toggle(key) {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  return (
    <section className="wall" aria-label="Your committee">
      <header className="wall-head">
        <h2>Who sits in judgement</h2>
        <p className={tooFew ? "warn" : ""}>
          {tooFew
            ? `Seat at least ${MIN_AGENTS} members.`
            : `${n} seated, ${n * roundsFor(n)} turns of debate.${n > LARGE_COMMITTEE ? " Six to ten argue sharpest." : ""}`}
        </p>
      </header>

      <div className="wall-presets" role="radiogroup" aria-label="Ready made committees">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            role="radio"
            aria-checked={active?.id === p.id}
            className={active?.id === p.id ? "on" : ""}
            onClick={() => onChange(new Set(p.keys))}
            onMouseEnter={() => setPeek(p.id)}
            onMouseLeave={() => setPeek(null)}
            onFocus={() => setPeek(p.id)}
            onBlur={() => setPeek(null)}
          >
            {p.label}
          </button>
        ))}
      </div>
      <p className="wall-blurb" aria-live="polite">
        {shown ? shown.blurb : "Your own committee. Tap a portrait to seat or dismiss them."}
      </p>

      <div className="wall-grid">
        {AGENT_ORDER.map((key) => {
          const on = selected.has(key);
          return (
            <div key={key} className={`wall-seat${on ? " wall-seat--on" : ""}`}>
              <button type="button" className="wall-plate" aria-pressed={on} aria-label={`${AGENT_META[key].name}, ${AGENT_META[key].role}. ${on ? "Seated" : "Not seated"}.`} onClick={() => toggle(key)}>
                <span className="fl-plate">
                  <Face memberKey={key} />
                </span>
                <span className="wall-cap">
                  <b>{shortName(key)}</b>
                  <span>{AGENT_META[key].role}</span>
                </span>
              </button>
              <button type="button" className="wall-bio" onClick={() => setBio(key)}>
                How they think
              </button>
            </div>
          );
        })}
      </div>
      <p className="wall-note">Founders and legends are builders, not stock pickers. Every member is an AI interpretation of how they thought, not their actual views.</p>

      <AgentBioModal agentKey={bio} onClose={() => setBio(null)} />
    </section>
  );
}
