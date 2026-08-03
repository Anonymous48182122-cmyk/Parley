import { useMemo } from "react";
import { createAvatar } from "@dicebear/core";
import * as bottts from "@dicebear/bottts";
import { AGENT_META, agentColor } from "../agentMeta.js";

const SIZE_PX = { sm: 28, md: 34, lg: 56 };

// Real investors get a commissioned illustrated portrait (frontend/public/avatars/*.webp)
// instead of a bot avatar — the Historian, Future Agent, Devil's Advocate, and CIO
// aren't real people, so they keep the procedurally generated bot.
const PORTRAIT_AGENTS = new Set(["buffett", "munger", "lynch", "jhunjhunwala", "simons", "ackman"]);

// Procedurally generated "AI bot" avatars (DiceBear, MIT-licensed, fully
// local/offline generation — no network call, no per-user tracking) rather
// than a likeness of the real investors: same seed always produces the same
// robot design, and baseColor is forced to match each agent's existing
// accent color so the avatar stays consistent with the rest of the app's
// color-coded identity system. Cached module-wide since the same agent's
// avatar renders many times across a page (chat, debate turns, chips).
const svgCache = new Map();

function resolveHex(agentKey) {
  const varName = agentKey ? `--agent-${agentKey}` : "--gold";
  const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  return (value || "#c9a04e").replace("#", "");
}

function getAvatarSvg(agentKey) {
  const seed = agentKey || "committee";
  const hex = resolveHex(agentKey);
  const cacheKey = `${seed}-${hex}`;
  if (svgCache.has(cacheKey)) return svgCache.get(cacheKey);
  const svg = createAvatar(bottts, {
    seed,
    baseColor: [hex],
    backgroundColor: ["transparent"],
  }).toString();
  svgCache.set(cacheKey, svg);
  return svg;
}

export default function AgentAvatar({ agentKey, size = "md", style }) {
  const meta = agentKey ? AGENT_META[agentKey] : null;
  // Guard against an unknown/null agentKey (e.g. the "whole committee"
  // pending state) — agentColor() would otherwise emit var(--agent-null),
  // an undefined custom property that breaks the var() fallback chain below.
  const color = meta ? agentColor(agentKey) : "var(--gold)";
  const isPortrait = Boolean(agentKey && PORTRAIT_AGENTS.has(agentKey));
  // Hooks must run unconditionally — skip the (cheap) bot generation when a
  // portrait will be used instead, rather than branching before this call.
  const svg = useMemo(() => (isPortrait ? null : getAvatarSvg(agentKey)), [agentKey, isPortrait]);

  return (
    <span
      className={`agent-avatar agent-avatar--${size}`}
      style={{ "--avatar-color": color, ...style }}
      title={meta?.name}
    >
      {isPortrait ? (
        <img
          className="agent-avatar-portrait"
          src={`/avatars/${agentKey}.webp`}
          alt={meta?.name ?? agentKey}
        />
      ) : (
        <span className="agent-avatar-bot" dangerouslySetInnerHTML={{ __html: svg }} />
      )}
    </span>
  );
}
