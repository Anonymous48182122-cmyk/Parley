import { STANCES, tallyFinal } from "../stance.js";

const ORDER = ["buy", "pass", "sell", "unclear"];

// The committee's calls at a glance: one segmented bar and a plain count. These are each agent's
// latest call, so once the debate has run they are the final calls, and the note under the bar
// says who changed their mind. `total` is how many agents are in the room, so the bar shows who
// has not weighed in yet.
export default function VoteBoard({ stances, debated, total }) {
  const counts = tallyFinal(stances);
  const moved = Object.values(stances || {}).filter((s) => s.changed).length;
  const decided = ORDER.reduce((sum, k) => sum + counts[k], 0);
  if (decided === 0) return null;
  const waiting = total && total > decided ? total - decided : 0;

  const summary = ORDER.filter((k) => counts[k] > 0)
    .map((k) => `${counts[k]} ${STANCES[k].label}`)
    .join(", ");

  return (
    <div className="vote">
      <div className="vote-head">
        <span className="vote-title">{debated ? "The final vote" : "The vote"}</span>
        <span className="vote-sub">
          {decided}
          {total ? ` of ${total}` : ""} in
        </span>
      </div>
      <div className="vote-bar" role="img" aria-label={`${debated ? "Final" : "First pass"} votes: ${summary}`}>
        {ORDER.map(
          (k) =>
            counts[k] > 0 && (
              <span key={k} className="vote-seg" style={{ flexGrow: counts[k], background: STANCES[k].color }}>
                {counts[k]}
              </span>
            )
        )}
        {waiting > 0 && <span className="vote-seg vote-seg--pending" style={{ flexGrow: waiting }} />}
      </div>
      <div className="vote-legend">
        {ORDER.map(
          (k) =>
            counts[k] > 0 && (
              <span key={k}>
                <i style={{ background: STANCES[k].color }} />
                {counts[k]} {STANCES[k].label}
              </span>
            )
        )}
      </div>
      {debated && moved > 0 && (
        <div className="vote-moved">
          {moved === 1 ? "1 member changed their mind" : `${moved} members changed their mind`} during the debate. Their first call is shown on their card.
        </div>
      )}
    </div>
  );
}
