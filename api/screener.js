// Relay for Screener.in pages. The backend host (Render) is refused by Screener at the network
// level, so when a direct request fails the backend asks this function instead; it runs on
// Vercel's network (Mumbai) and fetches the same public pages Screener's robots.txt allows.
//
// GET /api/screener?u=/company/TCS/consolidated/
// GET /api/screener?u=/api/company/6599230/chart/?q=Price-DMA50-DMA200-Volume&days=400
//
// Only company pages and the company data endpoints are relayed, and responses are cached at
// the edge for an hour, so repeat analyses of a stock do not reach Screener at all.

import { timingSafeEqual } from "node:crypto";

// When SCREENER_RELAY_KEY is set on this project, only callers that send it get through, so the
// relay is not an open door to Screener for the whole internet. Unset, it stays open (as before).
function authorised(req) {
  const required = process.env.SCREENER_RELAY_KEY;
  if (!required) return true;
  const sent = String(req.headers["x-relay-key"] || "");
  const a = Buffer.from(sent);
  const b = Buffer.from(required);
  return a.length === b.length && timingSafeEqual(a, b);
}

const ALLOWED = /^\/(company\/[A-Za-z0-9&_.-]+\/(consolidated\/)?|api\/company\/(\d+\/(chart|peers|schedules)|search)\/)/;

// GET /api/screener?bse=list: the BSE's list of every listed equity, trimmed to the four fields
// the search needs. The BSE refuses the backend host (Render) outright, as Screener does.
async function bseList(res) {
  const upstream = await fetch(
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active",
    {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        Referer: "https://www.bseindia.com/",
      },
    }
  );
  if (!upstream.ok) {
    res.status(502).json({ error: `BSE answered ${upstream.status}` });
    return;
  }
  const rows = await upstream.json();
  res.setHeader("Cache-Control", "private, no-store");
  res.status(200).json(
    rows.map((r) => ({
      code: String(r.SCRIP_CD),
      symbol: r.scrip_id || "",
      name: r.Issuer_Name || r.Scrip_Name || "",
      isin: r.ISIN_NUMBER || "",
    }))
  );
}

export default async function handler(req, res) {
  if (!authorised(req)) {
    res.status(401).json({ error: "unauthorised" });
    return;
  }
  if (req.query.bse === "list") {
    try {
      await bseList(res);
    } catch (err) {
      res.status(502).json({ error: String(err).slice(0, 200) });
    }
    return;
  }
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
      // a shared edge cache must never hand a keyed response to a caller without the key
      res.setHeader(
        "Cache-Control",
        process.env.SCREENER_RELAY_KEY ? "private, no-store" : "public, s-maxage=3600, stale-while-revalidate=86400"
      );
    }
    res.send(body);
  } catch (err) {
    res.status(502).json({ error: String(err).slice(0, 200) });
  }
}
