import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { AGENT_META } from "../agentMeta.js";
import { startAnalysis, getAnalysis, clearCache, saveToHistory, getLatestForTicker } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import AgentAvatar from "./AgentAvatar.jsx";
import AgentCommitteeStrip from "./AgentCommitteeStrip.jsx";
import DebateMessage from "./DebateMessage.jsx";
import CIOMemo from "./CIOMemo.jsx";
import SectionLabel from "./SectionLabel.jsx";
import ChatPanel from "./ChatPanel.jsx";
import MarketSnapshot from "./MarketSnapshot.jsx";
import WhatChanged from "./WhatChanged.jsx";

function SaveToHistory({ ticker, job, crossExams }) {
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
        user_chat: job.user_chat,
        cross_exams: crossExams,
        market_data: job.market_data,
        verdict: job.verdict,
        conviction: job.conviction,
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

// Drives the persistent "where am I" strip — deliberately reuses the same
// job.current_stage/status fields the poll loop already tracks, rather than
// scroll-spying the page, since that's a more reliable progress signal than
// scroll position on a page whose content is still arriving.
const PHASE_ORDER = ["stage1", "debate", "cio"];
const PHASE_LABELS = { stage1: "First Pass", debate: "Debate", cio: "CIO Memo" };
const PHASE_ANCHORS = { stage1: "#stage1", debate: "#debate", cio: "#cio-memo" };

function PhaseStrip({ job }) {
  const currentIndex = PHASE_ORDER.indexOf(job.current_stage);
  const contentReady = {
    stage1: Object.keys(job.stage1 || {}).length > 0,
    debate: (job.debate || []).length > 0,
    cio: !!job.cio_memo,
  };

  return (
    <div className="phase-strip">
      {PHASE_ORDER.map((key, i) => {
        const done = job.status === "complete" || (currentIndex >= 0 && i < currentIndex);
        const current = i === currentIndex;
        const className = [
          "phase-step",
          done && "phase-step--done",
          current && "phase-step--current",
        ]
          .filter(Boolean)
          .join(" ");
        const label = `${done ? "✓ " : ""}${PHASE_LABELS[key]}`;
        return contentReady[key] ? (
          <a key={key} href={PHASE_ANCHORS[key]} className={className}>
            {label}
          </a>
        ) : (
          <span key={key} className={className}>
            {label}
          </span>
        );
      })}
      {contentReady.stage1 && (
        <a href="#ask-committee" className="phase-step">
          Ask the Committee
        </a>
      )}
    </div>
  );
}

function TypingIndicator({ agentKey }) {
  const meta = AGENT_META[agentKey];
  return (
    <div className="fade-in" style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--text-dim)" }}>
      <AgentAvatar agentKey={agentKey} size="md" style={{ opacity: 0.7 }} />
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
  const location = useLocation();
  const { session } = useAuth();
  const [job, setJob] = useState(null);
  const [fatalError, setFatalError] = useState(null);
  const [crossExams, setCrossExams] = useState({});
  const [previousEntry, setPreviousEntry] = useState(null);
  const pollRef = useRef(null);
  // From the committee picker on SearchPage — absent on a direct link/refresh,
  // in which case the backend falls back to its own default committee.
  const requestedAgents = location.state?.agents;

  function handleExamsChange(turn, exams) {
    setCrossExams((prev) => ({ ...prev, [turn]: exams }));
  }

  // Powers the "what changed since you last saved this" card — best-effort,
  // silently skipped for signed-out users or if there's simply no prior save.
  useEffect(() => {
    if (!session) {
      setPreviousEntry(null);
      return;
    }
    getLatestForTicker(session.access_token, ticker)
      .then(setPreviousEntry)
      .catch(() => setPreviousEntry(null));
  }, [ticker, session]);

  useEffect(() => {
    let cancelled = false;
    setJob(null);
    setFatalError(null);
    setCrossExams({});

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
        const initial = await startAnalysis(ticker, undefined, requestedAgents);
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
  }, [ticker, requestedAgents]);

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
      // Re-run with the same committee this job actually used, not whatever
      // (possibly stale) navigation state got us here.
      const initial = await startAnalysis(ticker, undefined, job?.agents || requestedAgents);
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

      {job?.agent_warning && (
        <div style={{ color: "var(--text-dim)", fontSize: "0.82rem", marginBottom: 20 }}>
          {job.agent_warning}
        </div>
      )}

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
          <MarketSnapshot data={job.market_data} />
          <WhatChanged previous={previousEntry} current={job} />
          <PhaseStrip job={job} />

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
            <section id="stage1" className="scroll-anchor" style={{ marginBottom: 40 }}>
              <SectionLabel>Independent First Pass</SectionLabel>
              <AgentCommitteeStrip stage1={job.stage1} />
            </section>
          )}

          {(job.debate || []).length > 0 && (
            <section id="debate" className="scroll-anchor" style={{ marginBottom: 40 }}>
              <SectionLabel>Live Debate</SectionLabel>
              <div className="card">
                {job.debate.map((turn) => (
                  <DebateMessage
                    key={turn.turn}
                    ticker={ticker}
                    turn={turn.turn}
                    agentKey={turn.agent}
                    text={turn.text}
                    initialExams={crossExams[turn.turn] || []}
                    onExamsChange={handleExamsChange}
                    agents={job.agents}
                  />
                ))}
                {job.status === "running" &&
                  job.current_stage === "debate" &&
                  job.debate.length < (job.turn_plan || []).length && (
                    <TypingIndicator agentKey={job.turn_plan[job.debate.length]} />
                  )}
              </div>
            </section>
          )}

          {(Object.keys(job.stage1 || {}).length > 0 || job.status === "complete") && (
            <div id="ask-committee" className="scroll-anchor">
              <ChatPanel
                ticker={ticker}
                initialChat={job.user_chat}
                ready={job.status !== "error"}
                agents={job.agents}
              />
            </div>
          )}

          {job.cio_memo && (
            <section id="cio-memo" className="scroll-anchor">
              <CIOMemo text={job.cio_memo} verdict={job.verdict} conviction={job.conviction} />
              <SaveToHistory ticker={ticker} job={job} crossExams={crossExams} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
