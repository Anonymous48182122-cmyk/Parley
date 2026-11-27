// The companies looked at on this device, newest first, with the committee's call, so the home page can show
// where the reader left off. Kept in the browser only.

const KEY = "parley.recent";
const MAX = 8;

export function listRecent() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v.filter((r) => r && r.ticker) : [];
  } catch {
    return [];
  }
}

export function addRecent(entry) {
  if (!entry?.ticker) return;
  const key = (r) => `${r.market || ""}:${String(r.ticker).toUpperCase()}`;
  const next = [{ ...entry, at: Date.now() }, ...listRecent().filter((r) => key(r) !== key(entry))].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // history on this device is a nicety
  }
}
