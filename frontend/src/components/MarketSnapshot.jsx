import Sparkline from "./Sparkline.jsx";

const CURRENCY_SYMBOLS = { USD: "$", INR: "₹" };

function formatPrice(price, currency) {
  if (price == null) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || "";
  return `${symbol}${price.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatMarketCap(marketCap, unitLabel) {
  if (marketCap == null) return null;
  if (unitLabel === "USD") {
    const abs = Math.abs(marketCap);
    if (abs >= 1e12) return `$${(marketCap / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `$${(marketCap / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `$${(marketCap / 1e6).toFixed(2)}M`;
    return `$${marketCap.toLocaleString()}`;
  }
  // India: Screener already reports this in crores, matching unit_label.
  return `₹${marketCap.toLocaleString("en-IN")} Cr.`;
}

// Ratios arrive as numbers from one source and as "29.85%" strings from another.
function asPercent(value) {
  if (value == null || value === "") return null;
  return typeof value === "string" ? value : `${value}%`;
}

// First of several possible keys that actually has a value, since the data sources name
// the same measure differently (and either one can be missing).
function pick(ratios, ...keys) {
  for (const key of keys) {
    if (ratios[key] != null && ratios[key] !== "") return ratios[key];
  }
  return null;
}

// Debt to equity arrives as a percent (162.07 means 1.62 times), which reads as a wrong
// number next to the 1.62 every other site shows.
function formatDebtToEquity(value) {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (n == null || Number.isNaN(n)) return null;
  return `${(n / 100).toFixed(2)}x`;
}

function formatAsOf(iso) {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function RangeBar({ low, high, current, currency }) {
  if (low == null || high == null || current == null || high <= low) return null;
  const pct = Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100));
  const belowHigh = ((high - current) / high) * 100;
  const symbol = CURRENCY_SYMBOLS[currency] || "";
  const caption = belowHigh < 0.5 ? "At its 52 week high" : `${belowHigh.toFixed(1)}% below its 52 week high`;

  return (
    <div className="range">
      <div className="range-title">52 week range</div>
      <div className="range-track">
        <div className="range-fill" style={{ width: `${pct}%` }} />
        <div className="range-dot" style={{ left: `${pct}%` }} />
      </div>
      <div className="range-labels">
        <span>
          {symbol}
          {low.toLocaleString()}
        </span>
        <span>{caption}</span>
        <span>
          {symbol}
          {high.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  if (value == null || value === "") return null;
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

function Move({ label, value }) {
  if (value == null) return null;
  const up = value >= 0;
  return (
    <span className={`move ${up ? "move--up" : "move--down"}`}>
      <span className="move-label">{label}</span>
      {up ? "+" : ""}
      {value}%
    </span>
  );
}

export default function MarketSnapshot({ data }) {
  if (!data) return null;

  const ratios = data.ratios || {};
  const tech = data.technicals || {};
  // Show the card whenever there is anything to show; it used to vanish whenever price and
  // market cap were both missing, which hid the ratios and price action still available.
  const hasAnything =
    data.price != null ||
    data.market_cap != null ||
    Object.keys(ratios).length > 0 ||
    Object.keys(tech).length > 0;
  if (!hasAnything) return null;

  // the last daily close stands in for the live price when only the history came through
  const price = data.price ?? tech.last ?? null;
  const currency = data.price_currency ?? data.currency;
  const symbol = CURRENCY_SYMBOLS[currency] || "";
  const sector = data.sector && data.sector !== "N/A" ? data.sector : null;

  // The range prefers the exchange's own 52 week figures and falls back to the one computed
  // from daily closes, so a stock missing either source still gets one.
  const low = ratios["52-Week Low"] ?? tech.low_52w ?? null;
  const high = ratios["52-Week High"] ?? tech.high_52w ?? null;
  const hasMoves = [tech.ret_1m, tech.ret_3m, tech.ret_6m, tech.ret_1y, tech.vs_dma200].some((v) => v != null);
  const industry = pick(ratios, "Industry");

  return (
    <div className="card snapshot fade-in">
      <div className="snapshot-hero">
        <div className="snapshot-price">
          <div className="snapshot-eyebrow">
            {sector || "Price"}
            {industry && sector ? <span> · {industry}</span> : null}
          </div>
          <div className="snapshot-price-value">{formatPrice(price, currency)}</div>
          {tech.as_of && <div className="snapshot-asof">As of the {formatAsOf(tech.as_of)} close</div>}
          {hasMoves && (
            <div className="snapshot-moves">
              <Move label="1M" value={tech.ret_1m} />
              <Move label="3M" value={tech.ret_3m} />
              <Move label="6M" value={tech.ret_6m} />
              <Move label="1Y" value={tech.ret_1y} />
            </div>
          )}
        </div>
        {tech.closes?.length > 5 && (
          <div className="snapshot-chart">
            <Sparkline values={tech.closes} symbol={symbol} />
          </div>
        )}
      </div>

      <div className="stat-grid">
        <Stat label="Market cap" value={formatMarketCap(data.market_cap, data.market_cap_unit ?? data.unit_label)} />
        <Stat label="P/E" value={pick(ratios, "P/E Ratio (Trailing)", "P/E Ratio")} />
        <Stat label="Forward P/E" value={pick(ratios, "P/E Ratio (Forward)")} />
        <Stat label="Dividend yield" value={pick(ratios, "Dividend Yield")} />
        <Stat label="ROCE" value={asPercent(pick(ratios, "ROCE", "ROCE %"))} />
        <Stat label="ROE" value={asPercent(pick(ratios, "Return on Equity", "ROE"))} />
        <Stat label="Book value" value={pick(ratios, "Book Value per Share")} />
        <Stat label="Debt / equity" value={formatDebtToEquity(pick(ratios, "Debt to Equity"))} />
        <Stat label="Beta" value={pick(ratios, "Beta", "Beta (1Y vs S&P 500)")} />
      </div>

      <RangeBar low={low} high={high} current={price} currency={currency} />

      {tech.vs_dma200 != null && (
        <div className="snapshot-dma">
          {tech.vs_dma200 >= 0 ? "Above" : "Below"} its 200 day average by{" "}
          <strong>{Math.abs(tech.vs_dma200)}%</strong>
        </div>
      )}
    </div>
  );
}
