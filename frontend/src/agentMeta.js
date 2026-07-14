// Mirrors agents/prompts.py AGENTS + AGENT_DISPLAY_NAMES on the backend —
// keep keys in sync if the backend list changes.
export const AGENT_ORDER = [
  "buffett",
  "munger",
  "lynch",
  "jhunjhunwala",
  "simons",
  "ackman",
  "historian",
  "future",
  "devils_advocate",
];

export const AGENT_META = {
  buffett: { name: "Warren Buffett", monogram: "WB", role: "Master Capital Allocator" },
  munger: { name: "Charlie Munger", monogram: "CM", role: "Chief Thinker" },
  lynch: { name: "Peter Lynch", monogram: "PL", role: "Growth Hunter" },
  jhunjhunwala: { name: "Rakesh Jhunjhunwala", monogram: "RJ", role: "India Specialist" },
  simons: { name: "Jim Simons", monogram: "JS", role: "Quantitative Intelligence" },
  ackman: { name: "Bill Ackman", monogram: "BA", role: "Activist" },
  historian: { name: "The Historian", monogram: "H", role: "Pattern Recognition" },
  future: { name: "The Future Agent", monogram: "FA", role: "10-20yr Horizon" },
  devils_advocate: { name: "The Devil's Advocate", monogram: "DA", role: "Bear Case" },
  cio: { name: "The CIO", monogram: "CIO", role: "Synthesizer" },
};

// Mirrors DEBATE_TURN_PLAN's agent order in agents/prompts.py — used only to
// show "X is thinking..." for whichever agent should speak next while polling.
export const DEBATE_TURN_AGENTS = [
  "buffett",
  "munger",
  "lynch",
  "devils_advocate",
  "buffett",
  "jhunjhunwala",
  "ackman",
  "historian",
  "future",
  "munger",
  "lynch",
  "devils_advocate",
];

export function agentColor(key) {
  return `var(--agent-${key})`;
}

export function agentName(key) {
  return AGENT_META[key]?.name ?? key;
}

// Builds a regex that matches any agent's display name (and common short
// forms) so mentions inside debate prose can be auto-highlighted.
const NAME_VARIANTS = Object.entries(AGENT_META).flatMap(([key, meta]) => {
  const variants = new Set([meta.name]);
  const lastWord = meta.name.split(" ").pop();
  if (lastWord && lastWord.length > 2) variants.add(lastWord);
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
