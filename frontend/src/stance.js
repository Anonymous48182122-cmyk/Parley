// Reads an agent's first pass write-up and works out where they landed: buy, pass or
// sell. The agents end with a "Verdict" section in plain prose, so this reads the text
// after the last "Verdict" (or, failing that, the end of the write-up) and takes the first
// clear call it finds, understanding simple negations: "I would not buy" is a pass, and
// "Buy is not warranted" is a pass.

export const STANCES = {
  buy: { id: "buy", label: "Buy", color: "var(--success)" },
  pass: { id: "pass", label: "Pass", color: "var(--gold)" },
  sell: { id: "sell", label: "Sell", color: "var(--danger)" },
  unclear: { id: "unclear", label: "Undecided", color: "var(--text-faint)" },
};

const CALL = /\b(strong buy|buy|accumulate|pass|sell|avoid|stay away|hold off|hold|wait)\b/g;
const NEGATION_BEFORE = /\b(not|never|no|don't|do not|won't|wouldn't|would not|cannot|can't|isn't|is not)\s+(a |an |to |really |be a )?$/;
const NEGATION_AFTER = /^\W*(is|are|would be)\s+(not|n't)\s+(warranted|justified|earned|supported)|^\W*isn't\s+(warranted|justified)/;

function classify(segment) {
  CALL.lastIndex = 0;
  let m;
  while ((m = CALL.exec(segment))) {
    const word = m[1];
    const before = segment.slice(Math.max(0, m.index - 18), m.index);
    const after = segment.slice(m.index + word.length, m.index + word.length + 30);
    const buyLike = word === "buy" || word === "strong buy" || word === "accumulate";
    const negated = NEGATION_BEFORE.test(before) || NEGATION_AFTER.test(after);
    if (buyLike) return negated ? STANCES.pass : STANCES.buy;
    if (negated) continue; // "not a sell" says nothing about what they will do
    if (word === "sell" || word === "avoid") return STANCES.sell;
    return STANCES.pass; // pass, hold, hold off, wait, stay away
  }
  return null;
}

export function parseStance(text) {
  if (!text) return STANCES.unclear;
  const lower = text.toLowerCase().replace(/[*#_`]+/g, " ").replace(/\s+/g, " ");
  const at = lower.lastIndexOf("verdict");
  if (at !== -1) {
    const found = classify(lower.slice(at + "verdict".length).replace(/^[\s:|>\-]+/, "").slice(0, 700));
    if (found) return found;
  }
  return classify(lower.slice(-500)) || STANCES.unclear;
}

// Counts for the vote board.
export function tally(stage1) {
  const counts = { buy: 0, pass: 0, sell: 0, unclear: 0 };
  for (const text of Object.values(stage1 || {})) counts[parseStance(text).id] += 1;
  return counts;
}

// Where each agent stands once the debate is over. `opening` is the first pass call, `final` is
// the verdict on the agent's last debate turn that states one (the opening call when none does),
// and `changed` is true when they moved. The vote board, the chips and the CIO's vote count all
// use `final`, so the page never shows a call the agent has since dropped.
export function finalStances(stage1, debate) {
  const lastCall = {};
  for (const turn of debate || []) {
    const found = parseStance(turn.text);
    if (found.id !== "unclear") lastCall[turn.agent] = found;
  }
  const out = {};
  for (const [agent, text] of Object.entries(stage1 || {})) {
    const opening = parseStance(text);
    const final = lastCall[agent] || opening;
    out[agent] = { opening, final, changed: final.id !== opening.id && opening.id !== "unclear" };
  }
  return out;
}

export function tallyFinal(stances) {
  const counts = { buy: 0, pass: 0, sell: 0, unclear: 0 };
  for (const s of Object.values(stances || {})) counts[s.final.id] += 1;
  return counts;
}
