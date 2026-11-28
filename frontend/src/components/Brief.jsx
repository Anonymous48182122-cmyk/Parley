import "../brief.css";
import { useEffect, useState } from "react";
import { spokenBrief } from "../brief.js";
import { shareVerdict } from "../shareCard.js";
import Jargon from "./Jargon.jsx";

// The Brief: what a reader needs after seeing the floor, and nothing more. Three plain checks, the case for and
// against, what would change the committee's mind, and two ways to take it with you (a picture, or read aloud).

const ANSWER = { good: "Yes", ok: "Maybe", bad: "No", unknown: "Unclear" };

function ShareButton({ model, brief }) {
  const [state, setState] = useState("idle");
  async function go() {
    setState("working");
    try {
      const result = await shareVerdict({
        ticker: model.ticker, name: model.name, verdict: model.verdict, conviction: model.conviction,
        headline: brief.headline, lights: brief.lights, counts: brief.counts,
      });
      setState(result === "downloaded" ? "saved" : result === "shared" ? "sent" : "idle");
    } catch {
      setState("idle");
    }
    setTimeout(() => setState("idle"), 2500);
  }
  return (
    <button type="button" className="button-secondary" onClick={go} disabled={state === "working"}>
      {state === "working" ? "Making the picture" : state === "saved" ? "Saved to your downloads" : state === "sent" ? "Shared" : "Share as a picture"}
    </button>
  );
}

// Reads the brief aloud with the browser's own voice: free, private, and nothing to install.
function ListenButton({ model, brief }) {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => supported && window.speechSynthesis.cancel(), [supported]);
  if (!supported) return null;
  function toggle() {
    window.speechSynthesis.cancel();
    if (speaking) return setSpeaking(false);
    const u = new SpeechSynthesisUtterance(spokenBrief(model, brief));
    u.onend = u.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
    return setSpeaking(true);
  }
  return (
    <button type="button" className="button-secondary" onClick={toggle}>
      {speaking ? "Stop" : "Listen to the brief"}
    </button>
  );
}

function Case({ title, items, side }) {
  if (!items.length) return null;
  return (
    <div className={`bf-case bf-case--${side}`}>
      <h3>{title}</h3>
      <ol>
        {items.map((t) => (
          <li key={t}>
            <span>
              <Jargon text={t} />
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function Brief({ model, brief }) {
  if (!model.hasMemo && !Object.keys(model.stage1 || {}).length) return null;
  return (
    <div className="bf">
      <div className="bf-checks">
        {brief.lights.map((l) => (
          <div key={l.id} className={`bf-check bf-check--${l.tone}`}>
            <span>{l.question}</span>
            <b>{ANSWER[l.tone]}</b>
            <em>{l.line}</em>
          </div>
        ))}
      </div>

      <div className="bf-cases">
        <Case title="The case for" items={brief.forList} side="for" />
        <Case title="The case against" items={brief.againstList} side="against" />
      </div>

      {brief.changeMind && (
        <div className="bf-change">
          <span>What would change their mind</span>
          <p>
            <Jargon text={brief.changeMind} />
          </p>
        </div>
      )}

      {model.hasMemo && (
        <div className="bf-actions">
          <ShareButton model={model} brief={brief} />
          <ListenButton model={model} brief={brief} />
          <small>The committee's view, not advice.</small>
        </div>
      )}
    </div>
  );
}
