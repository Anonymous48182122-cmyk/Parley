// A small curated list of well-known tickers, bundled directly in the app so
// the very first keystroke gets an instant match with zero network round
// trip — the full backend search (SEC's ~10k + NSE's ~2k tickers) still runs
// in parallel and supplements/overtakes these as it comes back, but the user
// never has to stare at an empty dropdown while that request is in flight
// (which is especially slow right after a cold start on a free-tier host).
export const POPULAR_TICKERS = [
  // US — mega-cap tech
  { ticker: "AAPL", name: "Apple Inc.", market: "US" },
  { ticker: "MSFT", name: "Microsoft Corporation", market: "US" },
  { ticker: "GOOGL", name: "Alphabet Inc.", market: "US" },
  { ticker: "AMZN", name: "Amazon.com, Inc.", market: "US" },
  { ticker: "META", name: "Meta Platforms, Inc.", market: "US" },
  { ticker: "NVDA", name: "NVIDIA Corporation", market: "US" },
  { ticker: "TSLA", name: "Tesla, Inc.", market: "US" },
  { ticker: "NFLX", name: "Netflix, Inc.", market: "US" },
  { ticker: "AMD", name: "Advanced Micro Devices, Inc.", market: "US" },
  { ticker: "INTC", name: "Intel Corporation", market: "US" },
  { ticker: "ORCL", name: "Oracle Corporation", market: "US" },
  { ticker: "CRM", name: "Salesforce, Inc.", market: "US" },
  { ticker: "ADBE", name: "Adobe Inc.", market: "US" },
  { ticker: "PYPL", name: "PayPal Holdings, Inc.", market: "US" },
  { ticker: "UBER", name: "Uber Technologies, Inc.", market: "US" },
  { ticker: "ABNB", name: "Airbnb, Inc.", market: "US" },
  { ticker: "PLTR", name: "Palantir Technologies Inc.", market: "US" },
  { ticker: "COIN", name: "Coinbase Global, Inc.", market: "US" },
  { ticker: "SQ", name: "Block, Inc.", market: "US" },
  { ticker: "SHOP", name: "Shopify Inc.", market: "US" },
  { ticker: "IBM", name: "International Business Machines Corporation", market: "US" },
  { ticker: "QCOM", name: "QUALCOMM Incorporated", market: "US" },
  { ticker: "AVGO", name: "Broadcom Inc.", market: "US" },
  // US — blue chip / other majors
  { ticker: "JPM", name: "JPMorgan Chase & Co.", market: "US" },
  { ticker: "BAC", name: "Bank of America Corporation", market: "US" },
  { ticker: "WMT", name: "Walmart Inc.", market: "US" },
  { ticker: "KO", name: "The Coca-Cola Company", market: "US" },
  { ticker: "PEP", name: "PepsiCo, Inc.", market: "US" },
  { ticker: "MCD", name: "McDonald's Corporation", market: "US" },
  { ticker: "DIS", name: "The Walt Disney Company", market: "US" },
  { ticker: "NKE", name: "NIKE, Inc.", market: "US" },
  { ticker: "V", name: "Visa Inc.", market: "US" },
  { ticker: "MA", name: "Mastercard Incorporated", market: "US" },
  { ticker: "JNJ", name: "Johnson & Johnson", market: "US" },
  { ticker: "PG", name: "The Procter & Gamble Company", market: "US" },
  { ticker: "XOM", name: "Exxon Mobil Corporation", market: "US" },
  { ticker: "CVX", name: "Chevron Corporation", market: "US" },
  { ticker: "BA", name: "The Boeing Company", market: "US" },
  { ticker: "F", name: "Ford Motor Company", market: "US" },
  { ticker: "GM", name: "General Motors Company", market: "US" },
  { ticker: "T", name: "AT&T Inc.", market: "US" },
  { ticker: "HD", name: "The Home Depot, Inc.", market: "US" },
  { ticker: "COST", name: "Costco Wholesale Corporation", market: "US" },
  { ticker: "SBUX", name: "Starbucks Corporation", market: "US" },
  // India — Nifty50-ish majors
  { ticker: "RELIANCE", name: "Reliance Industries Limited", market: "India" },
  { ticker: "TCS", name: "Tata Consultancy Services Limited", market: "India" },
  { ticker: "INFY", name: "Infosys Limited", market: "India" },
  { ticker: "HDFCBANK", name: "HDFC Bank Limited", market: "India" },
  { ticker: "ICICIBANK", name: "ICICI Bank Limited", market: "India" },
  { ticker: "SBIN", name: "State Bank of India", market: "India" },
  { ticker: "HINDUNILVR", name: "Hindustan Unilever Limited", market: "India" },
  { ticker: "ITC", name: "ITC Limited", market: "India" },
  { ticker: "KOTAKBANK", name: "Kotak Mahindra Bank Limited", market: "India" },
  { ticker: "BHARTIARTL", name: "Bharti Airtel Limited", market: "India" },
  { ticker: "LT", name: "Larsen & Toubro Limited", market: "India" },
  { ticker: "AXISBANK", name: "Axis Bank Limited", market: "India" },
  { ticker: "ASIANPAINT", name: "Asian Paints Limited", market: "India" },
  { ticker: "MARUTI", name: "Maruti Suzuki India Limited", market: "India" },
  { ticker: "SUNPHARMA", name: "Sun Pharmaceutical Industries Limited", market: "India" },
  { ticker: "TITAN", name: "Titan Company Limited", market: "India" },
  { ticker: "WIPRO", name: "Wipro Limited", market: "India" },
  { ticker: "ULTRACEMCO", name: "UltraTech Cement Limited", market: "India" },
  { ticker: "NESTLEIND", name: "Nestle India Limited", market: "India" },
  { ticker: "BAJFINANCE", name: "Bajaj Finance Limited", market: "India" },
  { ticker: "HCLTECH", name: "HCL Technologies Limited", market: "India" },
  { ticker: "ADANIENT", name: "Adani Enterprises Limited", market: "India" },
  { ticker: "TATASTEEL", name: "Tata Steel Limited", market: "India" },
  { ticker: "TATAMOTORS", name: "Tata Motors Limited", market: "India" },
  { ticker: "ONGC", name: "Oil and Natural Gas Corporation Limited", market: "India" },
  { ticker: "POWERGRID", name: "Power Grid Corporation of India Limited", market: "India" },
  { ticker: "NTPC", name: "NTPC Limited", market: "India" },
  { ticker: "COALINDIA", name: "Coal India Limited", market: "India" },
  { ticker: "DRREDDY", name: "Dr. Reddy's Laboratories Limited", market: "India" },
  { ticker: "CIPLA", name: "Cipla Limited", market: "India" },
  { ticker: "GRASIM", name: "Grasim Industries Limited", market: "India" },
  { ticker: "JSWSTEEL", name: "JSW Steel Limited", market: "India" },
  { ticker: "TECHM", name: "Tech Mahindra Limited", market: "India" },
  { ticker: "HDFCLIFE", name: "HDFC Life Insurance Company Limited", market: "India" },
  { ticker: "SBILIFE", name: "SBI Life Insurance Company Limited", market: "India" },
  { ticker: "BRITANNIA", name: "Britannia Industries Limited", market: "India" },
  { ticker: "EICHERMOT", name: "Eicher Motors Limited", market: "India" },
  { ticker: "HEROMOTOCO", name: "Hero MotoCorp Limited", market: "India" },
  { ticker: "BPCL", name: "Bharat Petroleum Corporation Limited", market: "India" },
  { ticker: "VEDL", name: "Vedanta Limited", market: "India" },
  { ticker: "ZOMATO", name: "Eternal Limited", market: "India" },
  { ticker: "PAYTM", name: "One97 Communications Limited", market: "India" },
  { ticker: "NYKAA", name: "FSN E-Commerce Ventures Limited", market: "India" },
  { ticker: "URBANCO", name: "Urban Company Limited", market: "India" },
  { ticker: "DMART", name: "Avenue Supermarts Limited", market: "India" },
];

function score(query, ticker, name) {
  if (ticker === query) return 0;
  if (ticker.startsWith(query)) return 1;
  if (name.startsWith(query)) return 2;
  if (ticker.includes(query)) return 3;
  if (name.includes(query)) return 4;
  return null;
}

export function searchLocal(query, limit = 8) {
  const q = query.trim().toUpperCase();
  if (!q) return [];
  const scored = [];
  for (const entry of POPULAR_TICKERS) {
    const s = score(q, entry.ticker, entry.name.toUpperCase());
    if (s !== null) scored.push([s, entry.ticker.length, entry]);
  }
  scored.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return scored.slice(0, limit).map((row) => row[2]);
}
