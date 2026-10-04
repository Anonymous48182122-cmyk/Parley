// Mirrors agents/prompts.py AGENTS + AGENT_DISPLAY_NAMES + AGENT_KIND on the
// backend — keep keys in sync if the backend list changes.
export const AGENT_ORDER = [
  "buffett",
  "munger",
  "lynch",
  "jhunjhunwala",
  "simons",
  "ackman",
  "graham",
  "marks",
  "pabrai",
  "burry",
  "sperandeo",
  "damani",
  "historian",
  "future",
  "bull_advocate",
  "devils_advocate",
];

// A debate needs at least this many agents to be a debate — mirrors
// agents/prompts.py's MIN_AGENTS. Used to gate the picker's "start" action.
export const MIN_AGENTS = 3;

// The ten agents a fresh committee run defaults to when nothing else was
// chosen — mirrors agents/prompts.py's DEFAULT_AGENTS.
export const DEFAULT_AGENTS = [
  "buffett", "munger", "lynch", "jhunjhunwala", "simons",
  "ackman", "historian", "future", "bull_advocate", "devils_advocate",
];

export const AGENT_META = {
  buffett: { name: "Warren Buffett", monogram: "WB", role: "Master Capital Allocator", kind: "investor" },
  munger: { name: "Charlie Munger", monogram: "CM", role: "Chief Thinker", kind: "investor" },
  lynch: { name: "Peter Lynch", monogram: "PL", role: "Growth Hunter", kind: "investor" },
  jhunjhunwala: { name: "Rakesh Jhunjhunwala", monogram: "RJ", role: "Big Bull", kind: "investor" },
  simons: { name: "Jim Simons", monogram: "JS", role: "Quantitative Intelligence", kind: "investor" },
  ackman: { name: "Bill Ackman", monogram: "BA", role: "Opportunist", kind: "investor" },
  graham: { name: "Benjamin Graham", monogram: "BG", role: "Father of Value Investing", kind: "investor" },
  marks: { name: "Howard Marks", monogram: "HM", role: "Cycle & Risk Reader", kind: "investor" },
  pabrai: { name: "Mohnish Pabrai", monogram: "MP", role: "Asymmetric Bettor", kind: "investor" },
  burry: { name: "Michael Burry", monogram: "MB", role: "Forensic Contrarian", kind: "investor" },
  sperandeo: { name: "Victor Sperandeo", monogram: "VS", role: "Trend & Risk Trader", kind: "investor" },
  damani: { name: "Radhakishan Damani", monogram: "RD", role: "Conservative Operator", kind: "investor" },
  historian: { name: "The Historian", monogram: "H", role: "Pattern Recognition", kind: "special" },
  future: { name: "The Future Agent", monogram: "FA", role: "10-20yr Horizon", kind: "special" },
  bull_advocate: { name: "The Bull Advocate", monogram: "BU", role: "Bull Case", kind: "special" },
  devils_advocate: { name: "The Devil's Advocate", monogram: "DA", role: "Bear Case", kind: "special" },
  cio: { name: "The CIO", monogram: "CIO", role: "Synthesizer", kind: "special" },
};

export function agentColor(key) {
  return `var(--agent-${key})`;
}

export function agentName(key) {
  return AGENT_META[key]?.name ?? key;
}

// Builds a regex that matches any agent's display name (and common short
// forms) so mentions inside debate prose can be auto-highlighted.
// A short form (the last word of a name) is only usable if it identifies exactly
// one agent — "Advocate" belongs to both the Bull and the Devil's Advocate, so
// highlighting a bare "Advocate" as either would be a guess.
const LAST_WORD_OWNERS = Object.values(AGENT_META).reduce((acc, meta) => {
  const w = meta.name.split(" ").pop();
  acc[w] = (acc[w] || 0) + 1;
  return acc;
}, {});

const NAME_VARIANTS = Object.entries(AGENT_META).flatMap(([key, meta]) => {
  const variants = new Set([meta.name]);
  const lastWord = meta.name.split(" ").pop();
  if (lastWord && lastWord.length > 2 && LAST_WORD_OWNERS[lastWord] === 1) variants.add(lastWord);
  return [...variants].map((variant) => ({ key, variant }));
});

NAME_VARIANTS.sort((a, b) => b.variant.length - a.variant.length);

const MENTION_PATTERN = new RegExp(
  `\\b(${NAME_VARIANTS.map((v) => v.variant.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`,
  "g"
);

export function splitMentions(text) {
  const parts = [];
  let lastIndex = 0;
  for (const match of text.matchAll(MENTION_PATTERN)) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index) });
    }
    const found = NAME_VARIANTS.find((v) => v.variant === match[0]);
    parts.push({ text: match[0], agentKey: found?.key });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex) });
  }
  return parts;
}
