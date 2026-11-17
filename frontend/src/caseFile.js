import { COUNTRY_NAMES } from "./countryNames.js";
import { currencySymbol } from "./currency.js";
import { deriveBrief } from "./brief.js";

// The company's case file: a short file on what it is, what its numbers really say, and the few things most
// people miss. Everything here is worked out from figures Parley already holds, never written by a model, so it is
// instant, free and can always be traced back to a number. Nothing is shown that the data cannot support.

function num(v) {
  if (v == null || v === "") return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const n = parseFloat(String(v).replace(/[,%]/g, ""));
  return Number.isFinite(n) ? n : null;
}

// "16.23B" -> 16230000000
function amount(v) {
  if (v == null || v === "") return null;
  if (typeof v === "number") return v;
  const m = String(v).trim().match(/^(-?[\d.,]+)\s*([KMBT]|Cr)?$/i);
  if (!m) return null;
  const n = parseFloat(m[1].replace(/,/g, ""));
  const mult = { K: 1e3, M: 1e6, B: 1e9, T: 1e12, CR: 1e7 }[(m[2] || "").toUpperCase()] || 1;
  return Number.isFinite(n) ? n * mult : null;
}

function money(n, currency) {
  if (n == null) return null;
  const sym = currencySymbol(currency || "USD");
  return `${sym}${Number(n).toLocaleString(undefined, { maximumFractionDigits: n >= 100 ? 0 : 2 })}`;
}

function pct(n, digits = 0) {
  return `${Number(n).toFixed(digits)}%`;
}

// What kind of size this company is. Only judged where the thresholds are well understood (US dollars, Indian crores).
function sizeClass(md) {
  const cap = num(md.market_cap);
  if (cap == null) return null;
  const unit = String(md.market_cap_unit || md.unit_label || "");
  if (unit.includes("Cr")) {
    return cap >= 500000 ? "Mega cap" : cap >= 80000 ? "Large cap" : cap >= 25000 ? "Mid cap" : cap >= 5000 ? "Small cap" : "Micro cap";
  }
  if (unit === "USD") {
    return cap >= 200e9 ? "Mega cap" : cap >= 10e9 ? "Large cap" : cap >= 2e9 ? "Mid cap" : cap >= 300e6 ? "Small cap" : "Micro cap";
  }
  return null;
}

const SIZE_NOTE = {
  "Mega cap": "One of the largest companies in its market. Steady, hard to move.",
  "Large cap": "A big, established company.",
  "Mid cap": "Established but still growing into its size.",
  "Small cap": "Small enough to grow fast, and to fall hard.",
  "Micro cap": "Very small. Few people follow it, so prices can be odd.",
};

function metric(bs, id) {
  return (bs?.metrics || []).find((m) => m.id === id) || null;
}

const STATUS_TONE = { good: "good", watch: "watch", bad: "bad", unknown: "info" };

function vitals(md, bs) {
  const r = md.ratios || {};
  const out = [];

  const pe = num(r["P/E Ratio (Trailing)"]);
  if (pe != null && pe > 0) {
    const tone = pe <= 15 ? "good" : pe <= 30 ? "watch" : "bad";
    out.push({
      label: "Price against profit", value: `${pe.toFixed(1)} times`, tone,
      line: `You pay ${pe.toFixed(0)} years of today's profit for the share. In other words, 100 invested buys about ${(100 / pe).toFixed(1)} of profit a year.`,
    });
  }

  const debt = metric(bs, "net_debt_years") || metric(bs, "debt_to_equity") || metric(bs, "leverage");
  if (debt) out.push({ label: debt.label, value: debt.display, tone: STATUS_TONE[debt.status] || "info", line: debt.explain });

  const ret = metric(bs, "returns_on_capital") || metric(bs, "roe");
  if (ret) out.push({ label: ret.label, value: ret.display, tone: STATUS_TONE[ret.status] || "info", line: ret.explain });
  else {
    const roe = num(r["Return on Equity"]);
    if (roe != null) out.push({ label: "Return on owners' money", value: pct(roe, 1), tone: roe >= 15 ? "good" : roe >= 8 ? "watch" : "bad", line: `Each 100 the owners put in earns ${roe.toFixed(0)} a year.` });
  }

  const growth = num(r["Revenue Growth (YoY, latest quarter)"]);
  if (growth != null) {
    out.push({
      label: "Sales growth", value: pct(growth, 1), tone: growth >= 10 ? "good" : growth >= 3 ? "watch" : "bad",
      line: growth < 0 ? "Sales are shrinking compared with a year ago." : `Sales are ${growth.toFixed(0)}% higher than a year ago, in the latest quarter.`,
    });
  }
  return out.slice(0, 6);
}

// The things worth knowing that a quick look misses. Each has a weight; the most telling few are kept.
function insights(model, md, flow, bs, brief) {
  const r = md.ratios || {};
  const t = md.technicals || {};
  const cur = md.price_currency || md.currency;
  const out = [];
  const add = (weight, tone, title, text) => out.push({ weight, tone, title, text });

  // a great business is not always a good buy
  const scores = Object.values(model.scorecards || {}).map((c) => c?.score).filter(Boolean);
  const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  if (avg != null && model.verdict) {
    if (avg >= 7 && model.verdict !== "BUY") {
      add(9, "watch", "A strong business is not the same as a good buy",
        `The committee rates the business ${avg.toFixed(1)} out of 10, yet its call is ${model.verdict}. The company is liked. The price is the problem.`);
    } else if (avg < 5 && model.verdict === "BUY") {
      add(9, "watch", "A cheap price on a weak business",
        `The business scores only ${avg.toFixed(1)} out of 10. The buy case rests on the price, which is riskier than it sounds.`);
    }
  }

  const cash = metric(bs, "cash_conversion");
  if (cash && (cash.status === "bad" || cash.status === "watch")) {
    const got = num(String(cash.display).split(" ")[0]);
    add(8, "bad", "Profit on paper, less cash in hand",
      `For every 1 of profit it reports, only ${got != null ? got.toFixed(2) : "part"} arrives as cash. Profit that does not arrive as cash is worth checking before trusting.`);
  } else if (cash && cash.status === "good") {
    add(5, "good", "The profit is real",
      `For every 1 of profit it reports, about ${(num(String(cash.display).split(" ")[0]) || 1).toFixed(2)} arrives as cash. Many companies cannot say that.`);
  }

  const pe = num(r["P/E Ratio (Trailing)"]);
  const range = num(t.range_position);
  if (pe != null && pe >= 30 && range != null && range >= 85) {
    add(8, "watch", "Good news is already in the price",
      `The share sits near its yearly high at ${pe.toFixed(0)} times profit. There is little room for a disappointment.`);
  }
  const below = num(t.pct_below_high);
  if (below != null && below >= 25) {
    add(8, "watch", "The crowd is nervous",
      `The share is down ${below.toFixed(0)}% from its yearly high. Either something is wrong, or the market is too scared. The debate shows which.`);
  }

  const ins = md.business_facts?.management?.insiders;
  if (ins) {
    if (ins.buys >= 5 && ins.buys >= 2 * Math.max(ins.sells, 1)) {
      add(7, "good", "The bosses are buying",
        `${ins.buys} insider purchases against ${ins.sells} sales in ${ins.window}. People who run the company rarely buy unless they expect the share to rise.`);
    } else if (ins.sells >= 10 && ins.sells >= 3 * Math.max(ins.buys, 1)) {
      add(7, "watch", "The bosses are mostly selling",
        `${ins.sells} insider sales against ${ins.buys} purchases in ${ins.window}. Selling has many reasons, but buying has only one.`);
    }
  }

  const prom = md.business_facts?.management?.promoters;
  if (prom && prom.now != null && prom.year_ago != null) {
    const d = prom.now - prom.year_ago;
    if (d <= -2) add(7, "bad", "The founding family has been selling", `The promoters hold ${pct(prom.now, 1)}, down ${Math.abs(d).toFixed(1)} points in a year.`);
    else if (d >= 1) add(7, "good", "The founding family has been buying", `The promoters hold ${pct(prom.now, 1)}, up ${d.toFixed(1)} points in a year.`);
  }

  const nd = metric(bs, "net_debt_years");
  const ndYears = nd ? num(String(nd.display).split(" ")[0]) : null;
  if (ndYears != null && ndYears >= 4) {
    add(7, "bad", "A heavy debt to carry", `It would take about ${ndYears.toFixed(1)} years of operating profit to repay what it owes.`);
  }

  const ocf = amount(r["Operating Cash Flow (TTM, Yahoo)"]);
  const fcf = amount(r["Free Cash Flow (TTM, Yahoo)"]);
  if (ocf && fcf != null && ocf > 0) {
    const kept = (fcf / ocf) * 100;
    if (kept < 35) add(6, "watch", "A business that eats its own cash", `Of every 100 of cash it earns, only ${Math.max(kept, 0).toFixed(0)} is left after investing in the business itself.`);
    else if (kept >= 80) add(6, "good", "A business that keeps its cash", `Of every 100 of cash it earns, ${kept.toFixed(0)} is left over after investing in the business.`);
  }

  const target = num(r["Analyst Mean Target Price"]);
  const price = num(md.price);
  const nAn = num(r["Number of Analysts"]);
  if (target && price && nAn >= 5) {
    const gap = ((target - price) / price) * 100;
    if (Math.abs(gap) >= 15) {
      add(6, gap > 0 ? "good" : "watch", gap > 0 ? "Analysts see room to rise" : "Analysts see it as too high",
        `${nAn} analysts average a target of ${money(target, cur)}, ${Math.abs(gap).toFixed(0)}% ${gap > 0 ? "above" : "below"} today's price.`);
    }
  }

  const short = num(r["Short Interest (% of float)"]);
  if (short != null && short >= 10) {
    add(6, "watch", "Professionals are betting against it", `${short.toFixed(0)}% of the shares people can trade are sold short, a bet that the price will fall.`);
  }

  const pay = md.business_facts?.management?.ceo_pay?.pct_of_profit;
  if (pay != null && pay >= 0.5) add(5, "watch", "The boss takes a big slice", `The chief executive's pay is ${pay.toFixed(1)}% of the company's profit. Check what that pay rewards.`);

  const vol = num(t.volatility_1y);
  if (vol != null && vol >= 40) add(4, "watch", "A bumpy ride", `The share price has swung about ${vol.toFixed(0)}% over the year. Expect it to test your nerves.`);
  const moat = model.businessCard?.moat;
  const op = flow?.operating;
  if (moat?.strength >= 8 && op != null && op >= 20) {
    add(4, "good", "The moat shows up in the margins", `Rivals struggle to copy it (${moat.type}), and it keeps ${op.toFixed(0)} of every 100 sold as operating profit.`);
  }
  void brief;
  return out.sort((a, b) => b.weight - a.weight).slice(0, 4);
}

function people(md) {
  const m = md.business_facts?.management;
  if (!m) return null;
  const leaders = (m.leaders || []).slice(0, 4).map((l) => ({
    name: l.name,
    tag: l.ceo ? "Chief executive" : l.founder ? "Founder" : l.role || "",
  }));
  const lines = [];
  if (m.insiders) lines.push(`${m.insiders.buys} insider purchases and ${m.insiders.sells} sales in the last ${m.insiders.window}.`);
  if (m.promoters?.now != null) lines.push(`Promoters hold ${pct(m.promoters.now, 1)}${m.promoters.year_ago != null ? `, against ${pct(m.promoters.year_ago, 1)} a year ago` : ""}.`);
  if (m.ceo_pay?.pct_of_profit != null && m.ceo_pay.pct_of_profit > 0) lines.push(`The chief executive's pay is ${m.ceo_pay.pct_of_profit.toFixed(2)}% of profit.`);
  return leaders.length || lines.length ? { leaders, lines } : null;
}

function mood(md) {
  const t = md.technicals;
  if (!t || t.range_position == null) return null;
  const tags = [];
  if (t.vs_dma200 != null) tags.push({ text: `${t.vs_dma200 >= 0 ? "Above" : "Below"} its 200 day average by ${Math.abs(t.vs_dma200).toFixed(0)}%`, tone: t.vs_dma200 >= 0 ? "good" : "bad" });
  if (t.ret_1y != null) tags.push({ text: `${t.ret_1y >= 0 ? "Up" : "Down"} ${Math.abs(t.ret_1y).toFixed(0)}% in a year`, tone: t.ret_1y >= 0 ? "good" : "bad" });
  if (t.volatility_1y != null) tags.push({ text: t.volatility_1y >= 35 ? "Wild swings" : t.volatility_1y >= 22 ? "Normal swings" : "Calm mover", tone: t.volatility_1y >= 35 ? "bad" : "info" });
  return { position: Math.max(0, Math.min(100, t.range_position)), low: t.low_52w, high: t.high_52w, tags, currency: md.price_currency || md.currency };
}

export function buildCaseFile(model) {
  const md = model.marketData;
  if (!md) return null;
  const bs = md.balance_sheet;
  const flow = md.business_facts?.money_flow;
  const brief = deriveBrief(model);
  const size = sizeClass(md);
  const country = COUNTRY_NAMES[(model.country || md.country || "").toUpperCase()];
  const sector = md.ratios?.Industry || md.sector;

  const identity = [
    sector && { label: "Does", value: sector },
    (country || model.exchange) && { label: "Listed", value: [country, model.exchange].filter(Boolean).join(", ") },
    size && { label: "Size", value: size, note: SIZE_NOTE[size] },
  ].filter(Boolean);

  const card = model.businessCard;
  return {
    name: model.name || model.ticker,
    ticker: String(model.ticker).toUpperCase(),
    identity,
    born: card?.one_breath || null,
    flow: flow && flow.net != null ? flow : null,
    vitals: vitals(md, bs),
    insights: insights(model, md, flow, bs, brief),
    people: people(md),
    mood: mood(md),
    verdict: model.hasMemo ? { call: model.verdict, conviction: model.conviction, headline: brief.headline } : null,
  };
}
