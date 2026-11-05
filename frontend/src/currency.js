// Currency symbols and compact money, for any currency a company might report or trade in.
const symbolCache = {};

export function currencySymbol(code) {
  if (!code) return "";
  if (symbolCache[code] !== undefined) return symbolCache[code];
  let symbol = code;
  try {
    const parts = new Intl.NumberFormat("en-US", { style: "currency", currency: code, currencyDisplay: "symbol" }).formatToParts(1);
    symbol = parts.find((p) => p.type === "currency")?.value || code;
  } catch {
    symbol = code;
  }
  // a three letter code reads better with a space ("CHF 87.23") than glued to the number
  symbolCache[code] = /^[A-Z]{3}$/.test(symbol) ? `${symbol} ` : symbol;
  return symbolCache[code];
}

// 41,611,905,457,429 yen -> "¥41.61T"
export function compactMoney(value, code) {
  if (value == null) return null;
  const sym = currencySymbol(code);
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${sym}${(value / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sym}${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sym}${(value / 1e6).toFixed(2)}M`;
  return `${sym}${value.toLocaleString()}`;
}
