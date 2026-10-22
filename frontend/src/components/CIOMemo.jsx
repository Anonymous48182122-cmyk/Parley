import { useEffect, useRef, useState } from "react";
import { STANCES, tally } from "../stance.js";
import AgentAvatar from "./AgentAvatar.jsx";
import FormattedText from "./FormattedText.jsx";

const VERDICT_COLORS = {
  BUY: "var(--success)",
  HOLD: "var(--gold)",
  SELL: "var(--danger)",
};

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// True once the element has scrolled into view, so the reveal plays when the reader arrives
// at the verdict and not while it is still off screen. Skipped for reduced motion.
function useReveal() {
  const ref = useRef(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
      setShown(true);
      return undefined;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.5 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, shown];
}

// Counts from 0 up to `target` once `active`, easing out, so the score lands rather than appears.
function useCountUp(target, active, ms = 1200) {
  const [value, setValue] = useState(prefersReducedMotion() ? target : 0);
  useEffect(() => {
    if (!active || target == null) return undefined;
    if (prefersReducedMotion()) {
      setValue(target);
      return undefined;
    }
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / ms);
      setValue(Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, ms]);
  return value;
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard access can be denied (permissions, insecure context); failing
      // silently is fine, the button just will not show "Copied"
    }
  }

  return (
    <button type="button" className="button-secondary" onClick={handleCopy} style={{ fontSize: "0.75rem", padding: "6px 14px" }}>
      {copied ? "Copied ✓" : "Copy memo"}
    </button>
  );
}

// A ring that fills to the conviction score, in the colour of the verdict.
function Gauge({ conviction, shown, color }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  const frac = shown ? Math.min(1, Math.max(0, (conviction ?? 0) / 10)) : 0;
  const counted = useCountUp(conviction, shown);
  return (
    <svg className="gauge" viewBox="0 0 120 120" role="img" aria-label={`Conviction ${conviction ?? "unknown"} out of 10`}>
      <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" />
      <circle
        cx="60"
        cy="60"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={`${c * frac} ${c}`}
        transform="rotate(-90 60 60)"
        className="gauge-arc"
      />
      <text x="60" y="62" textAnchor="middle" className="gauge-number" fill="currentColor">
        {conviction == null ? "–" : counted}
      </text>
      <text x="60" y="82" textAnchor="middle" className="gauge-of" fill="currentColor">
        of 10
      </text>
    </svg>
  );
}

export default function CIOMemo({ text, verdict, conviction, stage1 }) {
  const color = VERDICT_COLORS[verdict] || "var(--text-dim)";
  const counts = stage1 ? tally(stage1) : null;
  const votes = counts ? ["buy", "pass", "sell", "unclear"].filter((k) => counts[k] > 0) : [];
  const [heroRef, shown] = useReveal();

  return (
    <div className={`card-gold fade-in cio${shown ? " cio--shown" : ""}`}>
      <div className="cio-hero" ref={heroRef} style={{ "--verdict-color": color }}>
        <Gauge conviction={conviction} shown={shown} color={color} />
        <div className="cio-hero-text">
          <div className="cio-eyebrow">
            <AgentAvatar agentKey="cio" size="sm" /> The CIO's call
          </div>
          <div className="cio-verdict">{verdict || "No call"}</div>
          <div className="cio-sub">Conviction {conviction ?? "unknown"} of 10</div>
          <div className="cio-sub-note">How strongly the evidence backs this call, not how many agreed.</div>
          {votes.length > 0 && (
            <div className="cio-votes" aria-label="How the committee voted">
              {votes.map((k) => (
                <span key={k} style={{ color: STANCES[k].color }}>
                  <i style={{ background: STANCES[k].color }} />
                  {counts[k]} {STANCES[k].label}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="cio-actions">
          <CopyButton text={text} />
        </div>
      </div>

      <div className="cio-note">A synthesis, not a vote: a map of where the committee actually landed.</div>
      <div className="cio-body">
        <FormattedText text={text} accentColor="var(--gold)" />
      </div>
    </div>
  );
}
