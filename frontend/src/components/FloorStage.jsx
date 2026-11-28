import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SIDES, limitText, sideAt } from "../floor.js";
import { Face } from "./Floor.jsx";

// "Hear the argument": one member at a time takes the whole screen and says their piece, in large type. It plays
// on its own, can be paused or stepped through, and can read each line aloud with the browser's own voice.

const CALL = { for: "For owning it", wait: "Waiting", against: "Against" };

export default function FloorStage({ speakers, start = 0, autoStart = true, price, today, currency, onClose }) {
  const [at, setAt] = useState(start);
  const [playing, setPlaying] = useState(autoStart);
  const [voice, setVoice] = useState(false);
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const closeRef = useRef(null);
  const m = speakers[Math.min(at, speakers.length - 1)];
  const words = (m?.line || "").split(" ");
  const duration = 2600 + words.length * 230;
  const side = sideAt(m, price, today);

  const step = (d) => {
    const next = at + d;
    if (next >= speakers.length) return onClose();
    return setAt(Math.max(0, next));
  };

  useEffect(() => {
    closeRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
      if (canSpeak) window.speechSynthesis.cancel();
    };
  }, [canSpeak]);

  // without sound the clock moves on; with sound the voice does, when it finishes the line
  useEffect(() => {
    if (!playing || voice) return undefined;
    const t = setTimeout(() => step(1), duration);
    return () => clearTimeout(t);
  }, [at, playing, voice, duration]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!voice || !canSpeak) return undefined;
    window.speechSynthesis.cancel();
    if (!playing) return undefined;
    const u = new SpeechSynthesisUtterance(`${m.name}. ${m.line}`);
    let live = true;
    u.onend = () => live && step(1);
    window.speechSynthesis.speak(u);
    return () => {
      live = false;
      window.speechSynthesis.cancel();
    };
  }, [at, voice, playing]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    function key(e) {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === " " && e.target.tagName !== "BUTTON") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  });

  if (!m) return null;
  return createPortal(
    <div className={`fls fls--${side}${playing ? "" : " fls--paused"}`} role="dialog" aria-modal="true" aria-label={`${m.name} speaks`}>
      <div className="fls-bars" aria-hidden="true">
        {speakers.map((s, i) => (
          <i key={s.key} className={i < at ? "done" : i === at ? (playing && !voice ? "now" : "done") : ""} style={{ "--dur": `${duration}ms` }} />
        ))}
      </div>
      <button ref={closeRef} type="button" className="fls-close" onClick={onClose} aria-label="Close">
        &times;
      </button>
      <div className="fls-art" key={`art-${m.key}`}>
        <Face memberKey={m.key} />
      </div>
      <div className="fls-text">
        <div className="fls-who">{m.name}</div>
        <div className="fls-call">{CALL[side] || SIDES[1].label}</div>
        <blockquote key={m.key} aria-live="polite">
          {words.map((w, i) => (
            <span key={i} style={{ animationDelay: `${300 + i * 55}ms` }}>
              {w}{" "}
            </span>
          ))}
        </blockquote>
        <div className="fls-would">{limitText(m, currency)}</div>
        <div className="fls-ctl">
          <button type="button" onClick={() => step(-1)} disabled={at === 0}>Previous</button>
          <button type="button" onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
          <button type="button" onClick={() => step(1)}>{at === speakers.length - 1 ? "Finish" : "Next"}</button>
          {canSpeak && (
            <button type="button" aria-pressed={voice} onClick={() => { setVoice((v) => !v); setPlaying(true); }}>
              {voice ? "Sound off" : "Sound on"}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
