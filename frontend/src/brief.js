import { finalStances, tallyFinal } from "./stance.js";
import { currencySymbol } from "./currency.js";

// The plain words version of a run, for people who have a minute and no finance background.
//
// The server writes the wording in one extra call (model.plainBrief). Everything here still works without it:
// the lights come from the numbers, the reasons from the members' own scorecards, the lines from the votes. So
// a failed call only makes the wording a little plainer; it never leaves a hole.

function money(price, currency) {
  if (price == null) return null;
  return `${currencySymbol(currency || "USD")}${Number(price).toLocaleString(undefined, { maximumFractionDigits: price >= 100 ? 0 : 2 })}`;
}

export function businessWord(avg) {
  if (avg >= 8) return "An exceptional business";
  if (avg >= 6.5) return "A strong business";
  if (avg >= 5) return "A decent business";
  if (avg >= 3.5) return "A weak business";
  return "A troubled business";
}

function uniq(list) {
  const seen = new Set();
  return list.filter((x) => {
    const k = x.toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function average(scorecards) {
  const scores = Object.values(scorecards || {}).map((c) => c?.score).filter(Boolean);
  return scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
}

function buyZone(levels) {
  return (levels || []).filter((l) => l.side === "below").sort((a, b) => b.price - a.price)[0] || null;
}

// Three traffic lights: is it a good business, are the finances safe, is the price fair.
function lightsFor(model, counts) {
  const avg = average(model.scorecards);
  const lights = [];

  lights.push(
    avg == null
      ? { id: "business", question: "Good business?", tone: "unknown", line: "Still being rated" }
      : { id: "business", question: "Good business?", tone: avg >= 6.5 ? "good" : avg >= 5 ? "ok" : "bad", line: businessWord(avg), detail: `${avg.toFixed(1)} out of 10` }
  );

  const tone = model.balanceSheet?.verdict?.tone;
  const safety = { strong: ["good", "Looks financially solid"], mixed: ["ok", "Some strengths, some worries"], weak: ["bad", "Finances look stretched"] }[tone];
  lights.push(
    safety
      ? { id: "safety", question: "Safe finances?", tone: safety[0], line: safety[1] }
      : { id: "safety", question: "Safe finances?", tone: "unknown", line: "Not enough data to say" }
  );

  const zone = buyZone(model.priceLevels);
  const decided = counts.buy + counts.pass + counts.sell;
  let price = { id: "price", question: "Fair price?", tone: "unknown", line: "No clear call on price" };
  if (zone) {
    const away = Math.abs(zone.pct);
    price = away <= 5
      ? { id: "price", question: "Fair price?", tone: "good", line: "Close to what buyers want to pay" }
      : away <= 15
        ? { id: "price", question: "Fair price?", tone: "ok", line: `A bit high. Buyers want ${money(zone.price, model.currency)}` }
        : { id: "price", question: "Fair price?", tone: "bad", line: `Pricey. Buyers want ${money(zone.price, model.currency)}` };
  } else if (decided > 0) {
    price = counts.buy / decided >= 0.5
      ? { id: "price", question: "Fair price?", tone: "good", line: "Most members would buy today" }
      : counts.sell / decided >= 0.35
        ? { id: "price", question: "Fair price?", tone: "bad", line: "Too rich for many members" }
        : { id: "price", question: "Fair price?", tone: "ok", line: "Members are split on the price" };
  }
  lights.push(price);
  return lights;
}

function headlineFor(model, counts) {
  const zone = buyZone(model.priceLevels);
  const tail = zone ? ` The first members would step in near ${money(zone.price, model.currency)}.` : "";
  const base = {
    BUY: "The committee likes this one and would buy.",
    SELL: "The committee would stay away from this one.",
  }[model.verdict] || "The committee would wait. It is not a clear yes or no yet.";
  return base + (model.verdict === "BUY" ? "" : tail);
}

function reasons(model, stances) {
  const cards = Object.entries(model.scorecards || {}).filter(([, c]) => c);
  const best = [...cards].sort((a, b) => (b[1].score || 0) - (a[1].score || 0));
  const worst = [...cards].sort((a, b) => (a[1].score || 0) - (b[1].score || 0));
  const forList = uniq(best.map(([, c]) => c.great).filter(Boolean)).slice(0, 3);
  const againstList = uniq(
    worst.flatMap(([, c]) => [c.bad, c.gruesome].filter((x) => x && !/^nothing that scares me/i.test(x)))
  ).slice(0, 3);
  void stances;
  return { forList, againstList };
}

export function deriveBrief(model) {
  const stances = finalStances(model.stage1, model.debate);
  const counts = tallyFinal(stances);
  const pb = model.plainBrief;
  const fallback = reasons(model, stances);
  const zone = buyZone(model.priceLevels);

  const members = Object.keys(stances).map((agent) => {
    const side = stances[agent].final.id;
    const card = model.scorecards?.[agent];
    const line = pb?.members?.[agent] || (side === "buy" ? card?.great : side === "sell" ? card?.gruesome || card?.bad : card?.bad) || null;
    return { agent, side, line, changed: stances[agent].changed };
  });

  return {
    stances,
    counts,
    decided: Object.keys(stances).length,
    moved: members.filter((m) => m.changed).length,
    headline: pb?.headline || headlineFor(model, counts),
    plain: !!pb,
    lights: lightsFor(model, counts),
    forList: pb?.for?.length ? pb.for : fallback.forList,
    againstList: pb?.against?.length ? pb.against : fallback.againstList,
    changeMind: pb?.change_mind || (zone ? `If the price fell near ${money(zone.price, model.currency)}, the buyers would step in.` : null),
    members,
    zone,
    zoneText: zone ? money(zone.price, model.currency) : null,
  };
}

// What to say out loud: short, in the order a person would tell it.
export function spokenBrief(model, brief) {
  const parts = [`${String(model.ticker).toUpperCase()}. ${brief.headline}`];
  if (brief.forList.length) parts.push(`What the committee likes. ${brief.forList.join(". ")}.`);
  if (brief.againstList.length) parts.push(`What worries them. ${brief.againstList.join(". ")}.`);
  if (brief.changeMind) parts.push(`What would change their mind. ${brief.changeMind}`);
  parts.push("This is the committee's view, not advice.");
  return parts.join(" ");
}
