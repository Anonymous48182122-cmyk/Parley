import { useCallback } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import { DEFAULT_AGENTS, MIN_AGENTS } from "./agentMeta.js";

// The reader's chosen committee, kept on this device, and the one way to open a company's research, used by
// the home page and by the search box in the top bar so both behave the same.

const STORAGE_KEY = "parley.committee";

// The default committee before the Bull Advocate was added. The page saves the default on first visit, so every
// returning visitor has this exact set stored; treat it as "never customised" and move them to the new default.
const LEGACY_DEFAULT = ["buffett", "munger", "lynch", "jhunjhunwala", "simons", "ackman", "historian", "future", "devils_advocate"];

export function loadCommittee() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set(DEFAULT_AGENTS);
    const keys = JSON.parse(raw);
    const legacy = Array.isArray(keys) && keys.length === LEGACY_DEFAULT.length && LEGACY_DEFAULT.every((k) => keys.includes(k));
    if (!Array.isArray(keys) || keys.length < MIN_AGENTS || legacy) return new Set(DEFAULT_AGENTS);
    return new Set(keys);
  } catch {
    return new Set(DEFAULT_AGENTS);
  }
}

export function saveCommittee(selected) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...selected]));
  } catch {
    // remembering the committee is a nicety
  }
}

export function useOpenResearch() {
  const navigate = useNavigate();
  return useCallback(
    (value, market, agents) => {
      const clean = String(value || "").trim().toUpperCase();
      const committee = [...(agents || loadCommittee())];
      if (!clean || committee.length < MIN_AGENTS) return;
      // the market the person picked travels with them, so a ticker that exists in two markets analyses the one they chose
      const go = () => navigate(`/analysis/${encodeURIComponent(clean)}`, { state: { agents: committee, market: market || undefined } });
      const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      if (document.startViewTransition && !calm) document.startViewTransition(() => flushSync(go));
      else go();
    },
    [navigate]
  );
}
