import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AGENT_META, AGENT_ORDER, DEBATE_TURN_AGENTS, agentColor } from "../agentMeta.js";
import { startAnalysis, getAnalysis, clearCache, saveToHistory } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import AgentCard from "./AgentCard.jsx";
import DebateMessage from "./DebateMessage.jsx";
import CIOMemo from "./CIOMemo.jsx";
import SectionLabel from "./SectionLabel.jsx";
import ChatPanel from "./ChatPanel.jsx";

function SaveToHistory({ ticker, job }) {
  const { session, user } = useAuth();
  const [status, setStatus] = useState("idle"); // idle | saving | saved | error
  const [error, setError] = useState(null);

  if (!user) {
    return (
      <div style={{ marginTop: 16, color: "var(--text-dim)", fontSize: "0.85rem" }}>
        <Link to="/auth" style={{ textDecoration: "underline" }}>
          Sign in
        </Link>{" "}
        to save this debate to your history.
      </div>
    );
  }

  async function handleSave() {
    setStatus("saving");
    setError(null);
    try {
      await saveToHistory(session.access_token, {
        ticker,
        market: job.market,
        cio_memo: job.cio_memo,
        stage1: job.stage1,
        debate: job.debate,
      });
      setStatus("saved");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <div style={{ marginTop: 16 }}>
      <button className="button-secondary" onClick={handleSave} disabled={status === "saving" || status === "saved"}>
        {status === "saved" ? "Saved ✓" : status === "saving" ? "Saving…" : "Save to History"}
      </button>
      {status === "error" && (
        <span style={{ color: "var(--danger)", fontSize: "0.85rem", marginLeft: 10 }}>{error}</span>
      )}
    </div>
  );
}

const POLL_INTERVAL_MS = 1500;

const STAGE_LABELS = {
  fetching_data: "Fetching financials…",
  stage1: "Independent first pass",
  debate: "Live debate",
  cio: "CIO synthesizing the memo",
};

function TypingIndicator({ agentKey }) {
  const meta = AGENT_META[agentKey];
  return (
    <div className="fade-in" style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--text-dim)" }}>
      <span className="monogram" style={{ background: agentColor(agentKey), opacity: 0.7 }}>
        {meta.monogram}
      </span>
      <span style={{ fontSize: "0.92rem" }}>{meta.name} is weighing in</span>
      <span className="typing-dots">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

export default function CommitteePage() {
  const { ticker } = useParams();
  const [job, setJob] = useState(null);
  const [fatalError, setFatalError] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setJob(null);
    setFatalError(null);

    async function poll() {
      try {
        const data = await getAnalysis(ticker);
        if (cancelled) return;
        setJob(data);
        if (data.status !== "running") {
          clearInterval(pollRef.current);
        }
      } catch (err) {
        if (!cancelled) setFatalError(err.message);
        clearInterval(pollRef.current);
      }
    }

    async function begin() {
      try {
        const initial = await startAnalysis(ticker);
        if (cancelled) return;
        setJob(initial);
        if (initial.status === "running") {
          pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!cancelled) setFatalError(err.message);
      }
    }

    begin();
    return () => {
      cancelled = true;
      clearInterval(pollRef.current);
    };
  }, [ticker]);

  async function handleRetry() {
    clearInterval(pollRef.current);
    setJob(null);
    setFatalError(null);
    try {
      await clearCache(ticker);
    } catch {
      // best-effort — proceed to re-run regardless
    }
    try {
      const initial = await startAnalysis(ticker);
      setJob(initial);
      if (initial.status === "running") {
        pollRef.current = setInterval(async () => {
          try {
            const data = await getAnalysis(ticker);
            setJob(data);
            if (data.status !== "running") clearInterval(pollRef.current);
          } catch (err) {
            setFatalError(err.message);
            clearInterval(pollRef.current);
          }
        }, POLL_INTERVAL_MS);
      }
    } catch (err) {
      setFatalError(err.message);
    }
  }

  return (
    <div className="container">
      <Link to="/" style={{ color: "var(--text-faint)", fontSize: "0.85rem" }}>
        ← back to search
      </Link>

      <div style={{ display: "flex", alignItems: "baseline", gap: 12, margin: "16px 0 28px" }}>
        <h1 className="ticker" style={{ fontSize: "2rem" }}>
          {ticker.toUpperCase()}
        </h1>
        {job?.market && (
          <span className="pill" style={{ fontSize: "0.75rem" }}>
            {job.market}
          </span>
        )}
      </div>

      {fatalError && (
        <div className="card fade-in" style={{ borderColor: "var(--danger)", marginBottom: 20 }}>
          <div style={{ color: "var(--danger)", fontWeight: 600, marginBottom: 6 }}>
            Something went wrong
          </div>
          <div style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>{fatalError}</div>
        </div>
      )}

      {!job && !fatalError && (
        <div className="pulse" style={{ color: "var(--text-dim)" }}>
          Convening the committee…
        </div>
      )}

      {job && job.status === "error" && (
        <div className="card fade-in" style={{ borderColor: "var(--danger)", marginBottom: 20 }}>
          <div style={{ color: "var(--danger)", fontWeight: 600, marginBottom: 6 }}>
            Analysis failed
          </div>
          <div style={{ color: "var(--text-dim)", fontSize: "0.9rem", marginBottom: 14 }}>
            {job.error}
          </div>
          <button className="button-primary" onClick={handleRetry}>
            Retry
          </button>
        </div>
      )}

      {job && job.status !== "error" && (
        <>
          {job.status === "running" && (
            <div style={{ marginBottom: 32 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
                  {STAGE_LABELS[job.current_stage] || "Working…"}
                </span>
                <span style={{ color: "var(--text-faint)", fontSize: "0.85rem" }}>
                  {Math.round(job.progress * 100)}%
                </span>
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${job.progress * 100}%` }} />
              </div>
            </div>
          )}

          {Object.keys(job.stage1 || {}).length > 0 && (
            <section style={{ marginBottom: 40 }}>
              <SectionLabel>Independent First Pass</SectionLabel>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {AGENT_ORDER.filter((key) => job.stage1[key]).map((key) => (
                  <AgentCard key={key} agentKey={key} text={job.stage1[key]} />
                ))}
              </div>
            </section>
          )}

          {(job.debate || []).length > 0 && (
            <section style={{ marginBottom: 40 }}>
              <SectionLabel>Live Debate</SectionLabel>
              <div className="card">
                {job.debate.map((turn) => (
                  <DebateMessage
                    key={turn.turn}
                    ticker={ticker}
                    turn={turn.turn}
                    agentKey={turn.agent}
                    text={turn.text}
                  />
                ))}
                {job.status === "running" &&
                  job.current_stage === "debate" &&
                  job.debate.length < DEBATE_TURN_AGENTS.length && (
                    <TypingIndicator agentKey={DEBATE_TURN_AGENTS[job.debate.length]} />
                  )}
              </div>
            </section>
          )}

          {(Object.keys(job.stage1 || {}).length > 0 || job.status === "complete") && (
            <ChatPanel
              ticker={ticker}
              initialChat={job.user_chat}
              ready={job.status !== "error"}
            />
          )}

          {job.cio_memo && (
            <section>
              <CIOMemo text={job.cio_memo} />
              <SaveToHistory ticker={ticker} job={job} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
