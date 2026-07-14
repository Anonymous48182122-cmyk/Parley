// Local dev keeps using Vite's /api proxy (see vite.config.js) to the local
// backend. Production build points at the real deployed backend URL, since
// there's no dev-server proxy once this is a static build on Vercel.
const BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export function searchTickers(query) {
  return fetch(`${BASE}/search?q=${encodeURIComponent(query)}`).then(handle);
}

export function startAnalysis(ticker, market) {
  return fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, market: market || null }),
  }).then(handle);
}

export function getAnalysis(ticker) {
  return fetch(`${BASE}/analysis/${encodeURIComponent(ticker)}`).then(handle);
}

export function clearCache(ticker) {
  return fetch(`${BASE}/analysis/${encodeURIComponent(ticker)}/cache`, {
    method: "DELETE",
  }).then(handle);
}

export function crossExam(ticker, agent, targetAgent, targetStatement) {
  return fetch(`${BASE}/analysis/${encodeURIComponent(ticker)}/cross-exam`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent,
      target_agent: targetAgent,
      target_statement: targetStatement,
    }),
  }).then(handle);
}

function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}

export function saveToHistory(token, { ticker, market, cio_memo, stage1, debate }) {
  return fetch(`${BASE}/history`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ ticker, market, cio_memo, stage1, debate }),
  }).then(handle);
}

export function listHistory(token) {
  return fetch(`${BASE}/history`, { headers: authHeaders(token) }).then(handle);
}

export function getHistoryEntry(token, id) {
  return fetch(`${BASE}/history/${encodeURIComponent(id)}`, { headers: authHeaders(token) }).then(handle);
}

export function deleteHistoryEntry(token, id) {
  return fetch(`${BASE}/history/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  }).then(handle);
}
