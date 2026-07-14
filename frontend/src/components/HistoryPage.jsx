import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { deleteHistoryEntry, listHistory } from "../api.js";

function excerpt(text, maxLen = 140) {
  if (!text) return "";
  const clean = text.replace(/[#*_]/g, "").trim();
  return clean.length > maxLen ? clean.slice(0, maxLen) + "…" : clean;
}

export default function HistoryPage() {
  const { session } = useAuth();
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!session) return;
    listHistory(session.access_token)
      .then(setEntries)
      .catch((err) => setError(err.message));
  }, [session]);

  async function handleDelete(id) {
    try {
      await deleteHistoryEntry(session.access_token, id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container">
      <Link to="/" style={{ color: "var(--text-faint)", fontSize: "0.85rem" }}>
        ← back to search
      </Link>

      <h1 style={{ fontSize: "2rem", margin: "18px 0 32px" }}>Your Saved Debates</h1>

      {error && (
        <div className="card" style={{ borderColor: "var(--danger)", marginBottom: 20, color: "var(--danger)" }}>
          {error}
        </div>
      )}

      {entries === null && !error && <div style={{ color: "var(--text-dim)" }}>Loading…</div>}

      {entries?.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
          <div style={{ color: "var(--text-dim)", fontSize: "0.95rem", lineHeight: 1.6 }}>
            No saved debates yet. Run a committee session and hit{" "}
            <span style={{ color: "var(--gold)" }}>Save to History</span> once the CIO memo is
            ready.
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {entries?.map((entry) => (
          <div key={entry.id} className="card card-interactive fade-in" style={{ display: "flex", gap: 12 }}>
            <Link to={`/history/${entry.id}`} style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
                <span className="ticker" style={{ fontWeight: 600, fontSize: "1.15rem" }}>
                  {entry.ticker}
                </span>
                {entry.market && <span className="pill" style={{ fontSize: "0.7rem" }}>{entry.market}</span>}
                <span style={{ color: "var(--text-faint)", fontSize: "0.75rem" }}>
                  {new Date(entry.created_at).toLocaleDateString()}
                </span>
              </div>
              <div style={{ color: "var(--text-dim)", fontSize: "0.88rem", lineHeight: 1.5 }}>
                {excerpt(entry.cio_memo)}
              </div>
            </Link>
            <button
              className="button-secondary"
              style={{ alignSelf: "flex-start", fontSize: "0.75rem", padding: "6px 12px" }}
              onClick={() => handleDelete(entry.id)}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
