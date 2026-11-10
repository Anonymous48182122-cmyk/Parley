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
  "musk",
  "bezos",
  "jobs",
  "dhirubhai",
  "thiel",
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

// One tap committees for the picker. Each answers a question a person actually has about a stock, so nobody has
// to know who thinks what. The first three follow Parley's own order of priorities: do not lose money, earn steadily,
// then reach for more. "classic" is the default roster. Each has a plain one line blurb the picker shows.
export const PRESETS = [
  { id: "classic", label: "Classic", keys: DEFAULT_AGENTS,
    blurb: "The balanced house committee. Ten voices, with a bull and a bear built in." },
  { id: "quick", label: "Quick Five", keys: ["buffett", "lynch", "simons", "bull_advocate", "devils_advocate"],
    blurb: "Five sharp voices. The fastest debate, and the lightest on free model limits." },
  { id: "safe", label: "Safe Hands", keys: ["graham", "buffett", "munger", "marks", "damani", "pabrai", "historian"],
    blurb: "Will I lose money? Minds that put losing less ahead of winning more." },
  { id: "compounders", label: "Steady Compounders", keys: ["buffett", "munger", "lynch", "jhunjhunwala", "bezos", "jobs", "future"],
    blurb: "Will it keep earning for years? Quality businesses and the patience to hold them." },
  { id: "moonshots", label: "Moonshots", keys: ["musk", "thiel", "bezos", "jobs", "future", "lynch", "bull_advocate"],
    blurb: "Could this be enormous? Big bets, long horizons and a taste for the improbable." },
  { id: "bears", label: "Bear Hunters", keys: ["burry", "marks", "graham", "historian", "sperandeo", "devils_advocate"],
    blurb: "What could go wrong? The members who are paid to find the crack." },
  { id: "timing", label: "Trader's Desk", keys: ["sperandeo", "simons", "marks", "ackman", "historian"],
    blurb: "Is the timing right? Trends, cycles and what the crowd is doing." },
  { id: "dalal", label: "Dalal Street", keys: ["jhunjhunwala", "damani", "dhirubhai", "pabrai", "lynch", "buffett"],
    blurb: "Think like the Indian market. Operators, bulls and patient owners. Made for Indian stocks." },
  { id: "founders", label: "Founders", keys: ["musk", "bezos", "jobs", "dhirubhai", "thiel"],
    blurb: "How would a builder see this? Five founders judge the business, not the share price." },
  { id: "everyone", label: "Everyone", keys: AGENT_ORDER,
    blurb: "All twenty one voices. The longest debate, the widest range of views." },
];

// Beyond this many the debate gets long and each voice gets thinner.
export const LARGE_COMMITTEE = 12;

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
  musk: { name: "Elon Musk", monogram: "EM", role: "First Principles Builder", kind: "legend" },
  bezos: { name: "Jeff Bezos", monogram: "JB", role: "Long Term Flywheel", kind: "legend" },
  jobs: { name: "Steve Jobs", monogram: "SJ", role: "Product & Focus", kind: "legend" },
  dhirubhai: { name: "Dhirubhai Ambani", monogram: "DA", role: "Scale & Shareholders", kind: "legend" },
  thiel: { name: "Peter Thiel", monogram: "PT", role: "Monopoly & Secrets", kind: "legend" },
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
