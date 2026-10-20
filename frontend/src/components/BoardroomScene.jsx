import { AGENT_META } from "../agentMeta.js";
import AgentAvatar from "./AgentAvatar.jsx";

// The lit room while an analysis runs. The committee takes its seats one by one, and each seat
// then shows what that person is actually doing right now: studying the numbers alone, finished
// with their first pass, speaking in the debate, or waiting while the CIO writes the verdict.
// Nothing here is decoration: every state comes from the live job.

const CAPTIONS = {
  convening: "The committee takes its seats",
  fetching_data: "Reading the filings, prices and ratios",
  stage1: "Each member studies the numbers alone",
  debate: "The debate is live",
  cio: "The CIO is writing the verdict",
};

function seatState(key, { stage, stage1, speaking }) {
  if (stage === "convening" || stage === "fetching_data") return "arriving";
  if (stage === "stage1") return stage1[key] ? "ready" : "thinking";
  if (stage === "debate") return speaking === key ? "speaking" : "ready";
  return "idle"; // cio: everyone has said their piece
}

export default function BoardroomScene({ job, agents, ticker }) {
  const list = (job?.agents && job.agents.length ? job.agents : agents) || [];
  if (list.length === 0) return null;

  const stage = job?.current_stage || "convening";
  const stage1 = job?.stage1 || {};
  const debate = job?.debate || [];
  const plan = job?.turn_plan || [];
  const speaking = stage === "debate" ? plan[debate.length] : null;
  const n = list.length;
  const seatSize = Math.min(9.6, 176 / n); // percent of the scene width

  const done = Object.keys(stage1).length;
  let detail = "";
  if (stage === "stage1") detail = `${done} of ${n} first passes in`;
  else if (stage === "debate") detail = `Turn ${Math.min(debate.length + 1, plan.length || debate.length + 1)} of ${plan.length || "?"}`;

  const speakerName = speaking ? AGENT_META[speaking]?.name : null;

  return (
    <div className="scene" role="img" aria-label={`Boardroom: ${CAPTIONS[stage] || "working"}`}>
      <div className="scene-light" aria-hidden="true" />
      <div className="scene-stage">
        <div className="scene-table" aria-hidden="true" />

        <div className="scene-center">
          <div className="scene-ticker">{ticker?.toUpperCase()}</div>
          <div className="scene-caption" key={stage}>
            {speakerName ? `${speakerName} has the floor` : CAPTIONS[stage] || "Working"}
          </div>
          {detail && <div className="scene-detail">{detail}</div>}
        </div>

        {list.map((key, i) => {
          const angle = ((-90 + (360 / n) * i) * Math.PI) / 180;
          const x = 50 + 43 * Math.cos(angle);
          const y = 50 + 39 * Math.sin(angle);
          const state = seatState(key, { stage, stage1, speaking });
          return (
            <div
              key={key}
              className={`scene-seat scene-seat--${state}`}
              style={{
                left: `${x}%`,
                top: `${y}%`,
                width: `${seatSize}%`,
                "--seat-color": `var(--agent-${key})`,
                "--arrive-delay": `${i * 90}ms`,
              }}
              title={AGENT_META[key]?.name}
            >
              <AgentAvatar agentKey={key} size="fill" />
              {state === "ready" && <span className="scene-check">✓</span>}
              {state === "speaking" && (
                <span className="scene-wave" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
