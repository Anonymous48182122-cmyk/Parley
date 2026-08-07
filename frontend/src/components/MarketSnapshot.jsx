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

function RangeBar({ low, high, current }) {
  if (low == null || high == null || current == null || high <= low) return null;
  const pct = Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100));
  return (
    <div style={{ marginTop: 14 }}>
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
        }}
      >
        <span>{low.toLocaleString()}</span>
        <span>52-week range</span>
        <span>{high.toLocaleString()}</span>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  if (value == null || value === "") return null;
  return (
    <div>
      <div style={{ fontSize: "0.7rem", color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </div>
      <div style={{ fontSize: "0.95rem", marginTop: 2 }}>{value}</div>
    </div>
  );
}

export default function MarketSnapshot({ data }) {
  if (!data || (data.price == null && data.market_cap == null)) return null;

  const ratios = data.ratios || {};
  const low = ratios["52-Week Low"];
  const high = ratios["52-Week High"];

  return (
    <div className="card fade-in" style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
        <Stat label="Price" value={formatPrice(data.price, data.currency)} />
        <Stat label="Market Cap" value={formatMarketCap(data.market_cap, data.unit_label)} />
        <Stat label="P/E (Trailing)" value={ratios["P/E Ratio (Trailing)"]} />
        <Stat label="Dividend Yield" value={ratios["Dividend Yield"]} />
        <Stat label="Sector" value={data.sector && data.sector !== "N/A" ? data.sector : null} />
      </div>
      <RangeBar low={low} high={high} current={data.price} />
    </div>
  );
}
