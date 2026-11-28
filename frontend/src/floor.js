import { AGENT_META, agentName, shortName } from "./agentMeta.js";
import { currencySymbol } from "./currency.js";
import { finalStances } from "./stance.js";

// The Floor's rules: where every member stands today, at what price each would cross to another side, and what
// the room would call at any price the reader tries.
//
// Nothing here is a new analysis. A member moves only when the price crosses a limit that member stated: at or
// below their buy price they are For, at or above their sell price they step back. At today's price everyone
// stands exactly where the debate left them.

export const SIDES = [
  { id: "for", label: "For" },
  { id: "wait", label: "Waiting" },
  { id: "against", label: "Against" },
];

const PORTRAITS = new Set([
  "buffett", "munger", "lynch", "jhunjhunwala", "simons", "ackman", "graham", "marks", "pabrai", "burry",
  "sperandeo", "damani", "musk", "bezos", "jobs", "dhirubhai", "thiel",
]);
const SYMBOLS = { historian: "§", future: "∞", bull_advocate: "▲", devils_advocate: "▼" };

export function portraitOf(key) {
  return PORTRAITS.has(key) ? `/avatars/${key}.webp` : null;
}

export function symbolOf(key) {
  return SYMBOLS[key] || (AGENT_META[key]?.monogram ?? "?");
}

export function money(value, currency) {
  if (value == null) return "";
  const n = Number(value);
  return `${currencySymbol(currency || "USD")}${n.toLocaleString(undefined, { minimumFractionDigits: n % 1 && n < 1000 ? 2 : 0, maximumFractionDigits: n >= 1000 ? 0 : 2 })}`;
}

const SIDE_OF = { buy: "for", pass: "wait", sell: "against", unclear: "wait" };

function sane(value, price) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 && price > 0 && n >= 0.4 * price && n <= 2.5 * price ? n : null;
}

// A member's buy and sell price: the two lines every member now states, or else the prices the older write ups
// named in passing.
function limitsOf(key, model) {
  const price = Number(model.price);
  const card = model.scorecards?.[key];
  let buy = sane(card?.buy_at, price);
  let sell = sane(card?.sell_at, price);
  if (buy == null && sell == null) {
    const name = agentName(key);
    const mine = (model.priceLevels || []).filter((l) => (l.who || []).some((w) => w === name || w === key));
    const below = mine.filter((l) => l.side === "below").map((l) => l.price);
    const above = mine.filter((l) => l.side === "above").map((l) => l.price);
    buy = below.length ? Math.max(...below) : null;
    sell = above.length ? Math.min(...above) : null;
  }
  return { buy, sell };
}

// The last thing a member said, cut to something that can be read large.
function lastWords(key, model, limit = 190) {
  const turn = [...(model.debate || [])].reverse().find((t) => t.agent === key);
  const raw = (turn?.text || model.stage1?.[key] || "").replace(/[*#_`>]+/g, " ").replace(/\s+/g, " ").trim();
  if (!raw) return "";
  const sentences = raw.split(/(?<=[.!?])\s+/).filter((s) => s.length > 12 && !/^(what i see|verdict)\b/i.test(s));
  let out = "";
  for (const s of sentences) {
    if (out && (out + " " + s).length > limit) break;
    out = out ? `${out} ${s}` : s;
    if (out.length > 90) break;
  }
  out = out || raw;
  return out.length > limit ? `${out.slice(0, limit).replace(/\s+\S*$/, "")}...` : out;
}

export function floorMembers(model) {
  const stances = finalStances(model.stage1, model.debate);
  const keys = model.agents?.length ? model.agents : Object.keys(model.stage1 || {});
  const spoken = new Set(Object.keys(model.stage1 || {}));
  return keys
    .filter((k) => AGENT_META[k] && (spoken.has(k) || model.status === "running"))
    .map((key) => {
      const heard = spoken.has(key);
      return {
        key,
        name: agentName(key),
        short: shortName(key),
        base: heard ? SIDE_OF[stances[key]?.final?.id] || "wait" : "reading",
        changedInDebate: !!stances[key]?.changed,
        ...(heard ? limitsOf(key, model) : { buy: null, sell: null }),
        line: heard ? model.plainBrief?.members?.[key] || lastWords(key, model) : "",
      };
    });
}

// Where a member stands if the share cost `p`. `today` is today's price.
export function sideAt(m, p, today) {
  if (m.base === "reading" || !today || p === today) return m.base;
  const { buy, sell, base } = m;
  if (sell != null) {
    if (sell > today && p >= sell) return base === "for" ? "wait" : "against";
    if (sell <= today && base === "against" && p < sell) return "wait";
  }
  if (buy != null) {
    if (buy < today && p <= buy) return "for";
    if (buy >= today && base === "for" && p > buy) return "wait";
  }
  return base;
}

export function groupAt(members, p, today) {
  const groups = { for: [], wait: [], against: [], reading: [] };
  for (const m of members) groups[sideAt(m, p, today)].push(m);
  return groups;
}

// The room's call from its sides, the same rule the automatic summary uses.
export function roomCall(groups) {
  const n = groups.for.length + groups.wait.length + groups.against.length;
  if (!n) return "HOLD";
  if (groups.for.length / n > 0.5) return "BUY";
  if (groups.against.length / n >= 0.35) return "SELL";
  return "HOLD";
}

export function limitText(m, currency) {
  const parts = [];
  if (m.buy != null) parts.push(`would buy at ${money(m.buy, currency)} or less`);
  if (m.sell != null) parts.push(`would sell at ${money(m.sell, currency)} or more`);
  return parts.length ? `${m.short} ${parts.join(", and ")}.` : `${m.short} named no price. The view rests on the business.`;
}

// The range of prices the reader can try: wide enough to reach every limit near today's price.
export function priceRange(members, closes, price) {
  const near = members.flatMap((m) => [m.buy, m.sell]).filter((v) => v != null && Math.abs(v / price - 1) <= 0.5);
  const all = [...(closes || []), ...near, price].filter((v) => Number.isFinite(v) && v > 0);
  const lo = Math.min(...all, price * 0.8);
  const hi = Math.max(...all, price * 1.15);
  const pad = (hi - lo) * 0.06;
  return [Math.max(0, lo - pad), hi + pad];
}
