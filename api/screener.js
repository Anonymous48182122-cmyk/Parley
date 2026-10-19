// Relay for Screener.in pages. The backend host (Render) is refused by Screener at the network
// level, so when a direct request fails the backend asks this function instead; it runs on
// Vercel's network (Mumbai) and fetches the same public pages Screener's robots.txt allows.
//
// GET /api/screener?u=/company/TCS/consolidated/
// GET /api/screener?u=/api/company/6599230/chart/?q=Price-DMA50-DMA200-Volume&days=400
//
// Only company pages and the company data endpoints are relayed, and responses are cached at
// the edge for an hour, so repeat analyses of a stock do not reach Screener at all.

const ALLOWED = /^\/(company\/[A-Za-z0-9&_.-]+\/(consolidated\/)?|api\/company\/\d+\/(chart|peers|schedules)\/)/;

export default async function handler(req, res) {
  const target = typeof req.query.u === "string" ? req.query.u : "";
  if (!ALLOWED.test(target) || target.includes("..") || target.includes("//")) {
    res.status(400).json({ error: "path not allowed" });
    return;
  }
  try {
    const headers = {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      Accept: "text/html,application/json;q=0.9,*/*;q=0.8",
    };
    if (target.startsWith("/api/")) headers["X-Requested-With"] = "XMLHttpRequest";
    const upstream = await fetch("https://www.screener.in" + target, { headers, redirect: "follow" });
    const body = await upstream.text();
    res.status(upstream.status);
    res.setHeader("Content-Type", upstream.headers.get("content-type") || "text/plain");
    if (upstream.status === 200) {
      res.setHeader("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=86400");
    }
    res.send(body);
  } catch (err) {
    res.status(502).json({ error: String(err).slice(0, 200) });
  }
}
