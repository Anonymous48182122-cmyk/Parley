import { useEffect, useState } from "react";
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

// Seats are spread evenly along the length of the table's edge, not evenly by angle. Spreading by
// angle crowds the two ends of a wide oval (the seats there are a fraction of the gap apart) and a
// big committee overlapped itself. `aspect` is the stage's height over its width, and every
// distance below is in units of the stage width, so the seat size can follow the real spacing.
function seatLayout(n, aspect) {
  const rx = 0.43;
  const ry = 0.39 * aspect;
  const steps = 720;
  const pts = [];
  let length = 0;
  for (let i = 0; i <= steps; i++) {
    const t = ((-90 + (360 * i) / steps) * Math.PI) / 180;
    const p = { x: rx * Math.cos(t), y: ry * Math.sin(t) };
    if (i > 0) length += Math.hypot(p.x - pts[i - 1].x, p.y - pts[i - 1].y);
    pts.push({ ...p, at: length });
  }
  const gap = length / n;
  const seats = [];
  let j = 0;
  for (let i = 0; i < n; i++) {
    while (j < steps && pts[j].at < i * gap) j++;
    seats.push({ x: 50 + (pts[j].x * 100), y: 50 + (pts[j].y / aspect) * 100 });
  }
  return { seats, size: Math.min(9.6, gap * 100 * 0.88) };
}

function useStageAspect() {
  const query = "(max-width: 520px)";
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return narrow ? 1 / 1.35 : 0.5; // matches .scene-stage's aspect-ratio in theme.css
}

function seatState(key, { stage, stage1, speaking }) {
  if (stage === "convening" || stage === "fetching_data") return "arriving";
  if (stage === "stage1") return stage1[key] ? "ready" : "thinking";
  if (stage === "debate") return speaking === key ? "speaking" : "ready";
  return "idle"; // cio: everyone has said their piece
}

export default function BoardroomScene({ job, agents, ticker }) {
  const aspect = useStageAspect();
  const list = (job?.agents && job.agents.length ? job.agents : agents) || [];
  if (list.length === 0) return null;

  const stage = job?.current_stage || "convening";
  const stage1 = job?.stage1 || {};
  const debate = job?.debate || [];
  const plan = job?.turn_plan || [];
  const speaking = stage === "debate" ? plan[debate.length] : null;
  const n = list.length;
  const { seats, size: seatSize } = seatLayout(n, aspect);

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
          const { x, y } = seats[i];
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
