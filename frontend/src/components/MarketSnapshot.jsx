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
  // India: yfinance/Screener already report this in crores, matching unit_label.
  return `₹${marketCap.toLocaleString("en-IN")} Cr.`;
}

// Ratios arrive as numbers from one source and as "29.85%" strings from another.
function asPercent(value) {
  if (value == null || value === "") return null;
  return typeof value === "string" ? value : `${value}%`;
}

// First of several possible keys that actually has a value, since the two data
// sources name the same measure differently (and either one can be missing).
function pick(ratios, ...keys) {
  for (const key of keys) {
    if (ratios[key] != null && ratios[key] !== "") return ratios[key];
  }
  return null;
}

function RangeBar({ low, high, current, currency }) {
  if (low == null || high == null || current == null || high <= low) return null;
  const pct = Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100));
  const belowHigh = ((high - current) / high) * 100;
  const symbol = CURRENCY_SYMBOLS[currency] || "";
  let caption;
  if (belowHigh < 0.5) caption = "At its 52-week high";
  else caption = `${belowHigh.toFixed(1)}% below its 52-week high`;

  return (
    <div style={{ marginTop: 18 }}>
      <div
        style={{
          position: "relative",
          height: 4,
          borderRadius: 2,
          background: "var(--border-strong)",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: `calc(${pct}% - 6px)`,
            top: -4,
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "var(--gold)",
            border: "2px solid var(--surface)",
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.72rem",
          color: "var(--text-faint)",
          marginTop: 6,
          gap: 8,
        }}
      >
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
    <div>
      <div
        style={{
          fontSize: "0.7rem",
          color: "var(--text-faint)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "0.95rem", marginTop: 2 }}>{value}</div>
    </div>
  );
}

function Move({ label, value }) {
  if (value == null) return null;
  const up = value >= 0;
  return (
    <span style={{ fontSize: "0.78rem", color: "var(--text-faint)" }}>
      {label}{" "}
      <span style={{ color: up ? "var(--success)" : "var(--danger)", fontWeight: 600 }}>
        {up ? "+" : ""}
        {value}%
      </span>
    </span>
  );
}

export default function MarketSnapshot({ data }) {
  if (!data || (data.price == null && data.market_cap == null)) return null;

  const ratios = data.ratios || {};
  const tech = data.technicals || {};
  const sector = data.sector && data.sector !== "N/A" ? data.sector : null;

  // The range prefers the exchange's own 52-week figures and falls back to the
  // one computed from daily closes, so a stock missing either source still gets one.
  const low = ratios["52-Week Low"] ?? tech.low_52w ?? null;
  const high = ratios["52-Week High"] ?? tech.high_52w ?? null;
  const hasMoves = [tech.ret_1m, tech.ret_3m, tech.ret_6m, tech.ret_1y, tech.vs_dma200].some(
    (v) => v != null
  );

  return (
    <div className="card fade-in" style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "18px 26px" }}>
        <Stat label="Price" value={formatPrice(data.price, data.currency)} />
        <Stat label="Market Cap" value={formatMarketCap(data.market_cap, data.unit_label)} />
        <Stat label="P/E" value={pick(ratios, "P/E Ratio (Trailing)", "P/E Ratio")} />
        <Stat label="Forward P/E" value={pick(ratios, "P/E Ratio (Forward)")} />
        <Stat label="Dividend Yield" value={pick(ratios, "Dividend Yield")} />
        <Stat label="ROCE" value={asPercent(pick(ratios, "ROCE", "ROCE %"))} />
        <Stat label="ROE" value={asPercent(pick(ratios, "Return on Equity", "ROE"))} />
        <Stat label="Book Value" value={pick(ratios, "Book Value per Share")} />
        <Stat label="Debt / Equity" value={pick(ratios, "Debt to Equity")} />
        <Stat label="Beta" value={pick(ratios, "Beta")} />
        <Stat label="Sector" value={sector} />
        <Stat label="Industry" value={pick(ratios, "Industry")} />
      </div>

      <RangeBar low={low} high={high} current={data.price} currency={data.currency} />

      {hasMoves && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", marginTop: 14 }}>
          <Move label="1M" value={tech.ret_1m} />
          <Move label="3M" value={tech.ret_3m} />
          <Move label="6M" value={tech.ret_6m} />
          <Move label="1Y" value={tech.ret_1y} />
          {tech.vs_dma200 != null && (
            <span style={{ fontSize: "0.78rem", color: "var(--text-faint)" }}>
              {tech.vs_dma200 >= 0 ? "Above" : "Below"} 200-day average by{" "}
              <span style={{ color: "var(--text-dim)", fontWeight: 600 }}>
                {Math.abs(tech.vs_dma200)}%
              </span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
