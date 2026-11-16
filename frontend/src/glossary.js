// Plain words for the finance words people trip over. Each answer is one or two short sentences a beginner can
// hold in their head. A term can have several spellings; the first is the one shown as the title.
// Keep these short: they appear in a small card when someone taps the word.

export const GLOSSARY = [
  { terms: ["moat"], say: "What protects a company from rivals, like a famous brand or a product nobody else can copy. A wide moat keeps profits safe for years." },
  { terms: ["margin of safety"], say: "Buying well below what you think something is worth, so you are still fine if you are a bit wrong." },
  { terms: ["free cash flow", "cash flow"], say: "The real cash left over after the company pays its bills and its investments. Profit on paper can hide a lack of cash, so this is the honest number." },
  { terms: ["P/E", "price to earnings", "P/E ratio"], say: "How many years of today's profit you pay for the share. A high P/E means the price is rich compared with what the company earns." },
  { terms: ["forward P/E"], say: "The P/E using next year's expected profit instead of last year's." },
  { terms: ["ROE", "return on equity"], say: "How much profit the company earns on the money its owners put in. Higher is better, as long as it is not built on heavy borrowing." },
  { terms: ["return on capital", "ROIC", "ROCE"], say: "How much profit the company earns on all the money tied up in the business. It shows how good the company is at turning money into more money." },
  { terms: ["operating margin"], say: "Out of every 100 of sales, how much is left as profit from running the business, before interest and tax." },
  { terms: ["gross margin"], say: "Out of every 100 of sales, how much is left after paying only for making the product. Higher usually means more pricing power." },
  { terms: ["net margin", "profit margin"], say: "Out of every 100 of sales, how much finally ends up as profit." },
  { terms: ["EBITDA"], say: "Profit before interest, tax and wear and tear on equipment. A rough way to compare how much a business earns from its operations." },
  { terms: ["EPS", "earnings per share"], say: "The company's profit divided by the number of shares. It is the profit that belongs to one share." },
  { terms: ["market cap", "market capitalisation", "market capitalization"], say: "The price of the whole company on the stock market: the share price times the number of shares." },
  { terms: ["debt to equity", "D/E"], say: "How much the company has borrowed compared with what its owners have put in. A high number means it leans on loans." },
  { terms: ["interest cover", "interest coverage"], say: "How many times over the company's profit could pay its loan interest. Under 2 or 3 is a warning sign." },
  { terms: ["dividend yield", "dividend"], say: "The cash a company pays its shareholders each year, shown as a percentage of the share price." },
  { terms: ["buyback", "buybacks", "share buyback"], say: "When a company buys its own shares from the market. It shrinks the number of shares, so each one owns a bigger slice." },
  { terms: ["free float"], say: "The shares that ordinary investors can actually buy and sell, not held by insiders." },
  { terms: ["promoter", "promoters"], say: "The founding owners of an Indian company. When they hold a lot of the shares and do not sell, it is usually a good sign." },
  { terms: ["valuation"], say: "Whether the share price is cheap, fair or expensive compared with what the business is worth." },
  { terms: ["compounding", "compounder", "compounders"], say: "Profits that earn more profits, year after year, like interest on interest. The longer it runs, the bigger it gets." },
  { terms: ["cyclical"], say: "A business whose results rise and fall with the economy, like cars, steel or construction." },
  { terms: ["leverage", "leveraged"], say: "Using borrowed money to earn more. It boosts gains when things go well and makes losses worse when they do not." },
  { terms: ["working capital"], say: "The money tied up in the day to day running of a business, like stock waiting to be sold and bills waiting to be paid." },
  { terms: ["capex", "capital expenditure"], say: "Money spent on factories, machines and other things that will last for years." },
  { terms: ["balance sheet"], say: "A snapshot of what a company owns and what it owes at one moment." },
  { terms: ["short seller", "short selling"], say: "Someone who bets a share price will fall, by selling shares they borrowed and hoping to buy them back cheaper." },
  { terms: ["bull case"], say: "The best reasons to expect the share to do well." },
  { terms: ["bear case"], say: "The best reasons to expect the share to do badly." },
  { terms: ["conviction"], say: "How sure the committee is about its call, from 1 to 10." },
  { terms: ["52 week high", "52 week range"], say: "The highest price the share reached in the last year, or the range between its lowest and highest." },
  { terms: ["200 day average"], say: "The average share price over the last 200 trading days. Trading above it usually means the trend is up." },
  { terms: ["volatility", "volatile"], say: "How wildly the share price swings up and down." },
  { terms: ["beta"], say: "How much the share moves compared with the whole market. Above 1 means it swings more than the market." },
  { terms: ["dilution"], say: "When a company issues new shares, every existing share owns a smaller slice of the company." },
  { terms: ["insider buying", "insider selling"], say: "Company bosses buying or selling their own company's shares. Buying is usually a good sign. Selling has many possible reasons." },
];

const ENTRIES = [];
for (const entry of GLOSSARY) for (const term of entry.terms) ENTRIES.push({ term, say: entry.say });
// longest first, so "forward P/E" wins over "P/E" and "free cash flow" over "cash flow"
ENTRIES.sort((a, b) => b.term.length - a.term.length);

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
const PATTERN = new RegExp(`(?<![\\w])(${ENTRIES.map((e) => escape(e.term)).join("|")})(?![\\w])`, "gi");
const BY_TERM = new Map(ENTRIES.map((e) => [e.term.toLowerCase(), e.say]));

export function explain(term) {
  return BY_TERM.get(String(term).toLowerCase()) || null;
}

// Splits text into plain pieces and glossary words: [{ text }, { text, term }, ...]
export function splitJargon(text) {
  if (!text) return [];
  const out = [];
  let last = 0;
  PATTERN.lastIndex = 0;
  let m;
  while ((m = PATTERN.exec(text))) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    out.push({ text: m[0], term: m[0].toLowerCase() });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}
