import { useState } from "react";
import { agentColor, agentName, shortName } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";

// Where the room stands: every member placed under For, Not sure or Against. Tap a face to read their one line.

const SIDES = [
  { id: "buy", label: "For", cls: "buy" },
  { id: "pass", label: "Not sure", cls: "pass" },
  { id: "sell", label: "Against", cls: "sell" },
];

export default function RoomSpectrum({ brief }) {
  const [picked, setPicked] = useState(null);
  if (!brief?.decided) return null;
  const member = brief.members.find((m) => m.agent === picked);
  const undecided = brief.members.filter((m) => m.side === "unclear");

  return (
    <section className="spectrum" aria-label="Where the room stands">
      <div className="spectrum-title">Where the room stands</div>
      <div className="spectrum-bar" aria-hidden="true">
        {SIDES.map((s) => brief.counts[s.id] > 0 && <span key={s.id} className={`bar--${s.cls}`} style={{ flexGrow: brief.counts[s.id] }} />)}
      </div>
      <div className="spectrum-cols">
        {SIDES.map((s) => {
          const list = brief.members.filter((m) => m.side === s.id);
          return (
            <div key={s.id} className={`spectrum-col spectrum-col--${s.cls}`}>
              <div className="spectrum-head">
                {s.label} <b>{list.length}</b>
              </div>
              <div className="spectrum-faces">
                {list.map((m) => (
                  <button key={m.agent} type="button" className={picked === m.agent ? "on" : ""} style={{ "--member": agentColor(m.agent) }} aria-pressed={picked === m.agent} title={agentName(m.agent)} onClick={() => setPicked(picked === m.agent ? null : m.agent)}>
                    <AgentAvatar agentKey={m.agent} size="md" />
                    <span>{shortName(m.agent)}</span>
                    {m.changed && <i title="Changed their mind in the debate" />}
                  </button>
                ))}
                {!list.length && <em>Nobody</em>}
              </div>
            </div>
          );
        })}
      </div>
      {member && (
        <p className="spectrum-line" role="status">
          <b style={{ color: agentColor(member.agent) }}>{agentName(member.agent)}</b>
          {member.changed ? " changed their mind in the debate. " : " "}
          {member.line || "No short line for this member."}
        </p>
      )}
      {undecided.length > 0 && <p className="spectrum-note">{undecided.length} without a clear call.</p>}
    </section>
  );
}
