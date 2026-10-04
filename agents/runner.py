"""
Pipeline runner: Stage 1 (independent first pass) -> Stage 2 (free-form
debate, plus optional cross-examination round) -> Stage 3 (CIO synthesis).
Every stage accepts an `on_update(event_type, payload)` callback so a caller
(the API job store, or a plain CLI script) can observe progress turn-by-turn
instead of waiting for the whole run to finish.

Every stage also accepts `agent_keys` — the caller picks which agents sit on
the committee for this run (see agents.prompts.AGENTS/DEFAULT_AGENTS); the
debate turn plan is generated fresh per call from whichever subset is given
(agents.prompts.build_debate_turn_plan), not a fixed script.
"""

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import groq
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors as gemini_errors
from google.genai import types

from agents.prompts import (
    AGENT_DISPLAY_NAMES,
    DEFAULT_AGENTS,
    CIO_PROMPT_TEMPLATE,
    CIO_SYSTEM_PROMPT,
    CROSS_EXAM_TEMPLATE,
    DEBATE_TURN_TEMPLATE,
    STAGE1_OUTPUT_SPEC,
    STAGE1_PROMPT_TEMPLATE,
    SYSTEM_PROMPTS,
    USER_QUESTION_TEMPLATE,
    build_debate_turn_plan,
    roster_line,
)

load_dotenv()

log = logging.getLogger("parley.llm")

# Two independent free-tier providers, so a Gemini-wide outage/quota wall
# doesn't stall the whole run — Groq (aistudio.google.com/apikey and
# console.groq.com, both free, no credit card) picks up the slack. Free-tier
# model availability is genuinely unstable day to day (a model free today
# gets deprecated for new keys, or is simply overloaded), so each stage tries
# an ordered (provider, model) candidate list, falling through on
# "unavailable" (404) or a model staying overloaded (503/429) after retries.
#
# Refreshed against live probes (Sep 2026): the pro tier is quota-exhausted /
# withdrawn for free keys, several older ids 404, and Gemini flash models 503
# in bursts — while Groq's gpt-oss-120b answers in ~1s. A model that fails is
# put on a cooldown (see _cool_down) so later calls skip it instead of paying
# the failure again, which is what made whole debates crawl.
STAGE1_CANDIDATES = [
    ("gemini", "gemini-3.6-flash"),
    ("groq", "openai/gpt-oss-120b"),
    ("gemini", "gemini-3.7-flash"),
    ("gemini", "gemini-3.8-flash"),
    ("gemini", "gemini-3-flash-preview"),
    ("gemini", "gemini-3.5-flash"),
    ("groq", "openai/gpt-oss-20b"),
    ("groq", "qwen/qwen3.8-27b"),
    ("gemini", "gemini-3.1-flash-lite"),
]
DEBATE_CANDIDATES = STAGE1_CANDIDATES
CIO_CANDIDATES = [
    ("gemini", "gemini-3.6-flash"),
    ("groq", "openai/gpt-oss-120b"),
    ("gemini", "gemini-3.7-flash"),
    ("gemini", "gemini-3.8-flash"),
    ("gemini", "gemini-3-flash-preview"),
    ("gemini", "gemini-3.5-flash"),
    ("groq", "qwen/qwen3.8-27b"),
]

STAGE1_MAX_TOKENS = 1400
DEBATE_MAX_TOKENS = 300
CIO_MAX_TOKENS = 2500

# Only one retry on a transient error: with this many fallbacks, moving to the
# next model beats waiting on an overloaded one.
_MAX_RETRIES_PER_MODEL = 2

_COOLDOWN_SECONDS = {"transient": 60, "daily": 3 * 3600, "missing": 6 * 3600, "rejected": 30 * 60}
# Longest a single call will wait for a rate-limited pool to recover.
_MAX_WAIT_SECONDS = 150
# Groq's free tier meters ~8k tokens/minute per model and counts the request
# (input + max_tokens) against it, so anything bigger is rejected outright
# (HTTP 413) no matter how long we wait.
_GROQ_MAX_REQUEST_TOKENS = 7500
# A single request's hard cap. Without this, an overloaded Gemini endpoint has
# been observed to hang 170s+ before finally erroring — far worse than just
# failing fast and letting the pool move to the next candidate.
_REQUEST_TIMEOUT_SECONDS = 25
_cooldowns = {}
_cooldown_lock = threading.Lock()

_gemini_client = None
_groq_client = None
_client_lock = threading.Lock()


class AgentCallError(RuntimeError):
    """Raised when every candidate model/provider fails — surfaced to the API
    layer as a job error rather than silently faking a debate turn."""


def _get_gemini_client():
    global _gemini_client
    with _client_lock:
        if _gemini_client is None:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise AgentCallError("GEMINI_API_KEY is not set in the environment")
            _gemini_client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT_SECONDS * 1000),  # ms
            )
        return _gemini_client


def _get_groq_client():
    global _groq_client
    with _client_lock:
        if _groq_client is None:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise AgentCallError("GROQ_API_KEY is not set in the environment")
            # retries handled by _call; a fixed timeout instead of Groq's default
            # so a hung connection fails fast like the Gemini client above.
            _groq_client = groq.Groq(api_key=api_key, max_retries=0, timeout=_REQUEST_TIMEOUT_SECONDS)
        return _groq_client


def _call_gemini(model, system, user, max_tokens):
    response = _get_gemini_client().models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            # Gemini 3.x models spend max_output_tokens on hidden "thinking" by
            # default, silently truncating the visible answer. These are
            # short, voice-driven outputs that don't need chain-of-thought.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text


def _call_groq(model, system, user, max_tokens):
    extra = {}
    if model.startswith("openai/gpt-oss"):
        # These are reasoning models: at default effort they can spend the whole
        # (small) token budget thinking and return an empty visible answer.
        extra["reasoning_effort"] = "low"
    response = _get_groq_client().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **extra,
    )
    return response.choices[0].message.content


_GEMINI_TRANSIENT = (gemini_errors.ServerError,)
_GROQ_TRANSIENT = (groq.RateLimitError, groq.InternalServerError, groq.APIConnectionError, groq.APITimeoutError)
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_RETRY_HINT_RE = re.compile(r"(?:try again|retry) in (?:(\d+)m)?\s*(\d+(?:\.\d+)?)(ms|s)", re.IGNORECASE)


_NETWORK_ERRORS = (httpx.TransportError, OSError, TimeoutError)


def _classify_error(provider, exc):
    """transient = overload / rate limit (worth a brief retry and a cooldown);
    daily = a per-day quota that will not recover for hours; missing = model id
    gone for this key; rejected = request-level refusal."""
    if isinstance(exc, _NETWORK_ERRORS):
        # DNS/connection/timeout failures are a local or transit blip, not a
        # verdict on any particular model — never provider-specific.
        return "transient"
    if provider == "gemini":
        if isinstance(exc, _GEMINI_TRANSIENT):
            return "transient"
        if isinstance(exc, gemini_errors.ClientError):
            if exc.code == 429:
                return "daily" if "PerDay" in str(exc) else "transient"
            return "missing" if exc.code == 404 else "rejected"
        return "rejected"
    if isinstance(exc, _GROQ_TRANSIENT):
        return "daily" if "per day" in str(exc).lower() else "transient"
    return "missing" if isinstance(exc, groq.NotFoundError) else "rejected"


def _retry_hint(exc):
    """Seconds the provider says to wait ("Please retry in 58.8s"), if any."""
    match = _RETRY_HINT_RE.search(str(exc))
    if not match:
        return None
    minutes, amount, unit = match.groups()
    seconds = float(amount) / (1000 if unit.lower() == "ms" else 1)
    return seconds + 60 * int(minutes or 0)


def _cooldown_until(provider, model):
    with _cooldown_lock:
        return _cooldowns.get((provider, model), 0)


def _cool_down(provider, model, kind, hint=None):
    seconds = _COOLDOWN_SECONDS[kind]
    if kind == "transient" and hint:
        seconds = min(max(hint + 0.5, 2), _COOLDOWN_SECONDS["transient"])
    with _cooldown_lock:
        _cooldowns[(provider, model)] = time.time() + seconds


def _retry_delay(attempt, hint=None):
    if hint and hint <= 10:
        return hint + 0.5
    return min(30, 2**attempt)


def _try_model(provider, model, system, user, max_tokens):
    """One model, with a brief retry on transient errors. Returns the text, or
    (None, error) after putting the model on cooldown."""
    for attempt in range(_MAX_RETRIES_PER_MODEL):
        started = time.time()
        try:
            if provider == "gemini":
                text = _call_gemini(model, system, user, max_tokens)
            else:
                text = _call_groq(model, system, user, max_tokens)
            text = _THINK_RE.sub("", text or "").strip()
            if not text:
                log.warning("%s:%s empty reply after %.1fs", provider, model, time.time() - started)
                _cool_down(provider, model, "transient", 20)
                return None, f"{provider}:{model} returned no text (likely a safety-filter block)"
            log.info("%s:%s ok in %.1fs", provider, model, time.time() - started)
            return text, None
        except Exception as exc:  # noqa: BLE001 — deliberately broad, see module docstring
            kind = _classify_error(provider, exc)
            hint = _retry_hint(exc)
            log.warning("%s:%s %s (%s) after %.1fs: %.140s", provider, model, kind,
                        type(exc).__name__, time.time() - started, exc)
            if kind == "transient" and attempt < _MAX_RETRIES_PER_MODEL - 1 and (hint is None or hint <= 10):
                time.sleep(_retry_delay(attempt, hint))
                continue
            _cool_down(provider, model, kind, hint)
            return None, exc
    return None, "retries exhausted"


def _call(candidates, system, user, max_tokens, prefer_provider=None, max_wait=None):
    """Free-tier capacity is a pool of small buckets (Gemini: a handful of
    requests/day per model; Groq: ~8k tokens/min per model), so this treats the
    candidate list as a pool rather than a one-shot fallback chain:

    - models on cooldown are skipped, so a dead/exhausted one costs one failure
      per cooldown window instead of one per call;
    - if every model is cooling but some recover soon, wait for the earliest
      instead of failing — a slow answer beats a failed debate;
    - models that provably can't take the request (Groq's per-minute token cap)
      are skipped up front instead of failing after a wait;
    - `prefer_provider` moves that provider's models to the front (stable) to
      spread parallel calls across both providers' limits."""
    if isinstance(candidates, tuple):
        candidates = [candidates]
    if prefer_provider:
        candidates = sorted(candidates, key=lambda c: c[0] != prefer_provider)

    est_tokens = (len(system) + len(user)) / 3.5 + max_tokens
    fits = [c for c in candidates if c[0] != "groq" or est_tokens <= _GROQ_MAX_REQUEST_TOKENS]
    if fits:
        candidates = fits

    deadline = time.time() + (max_wait if max_wait is not None else _MAX_WAIT_SECONDS)
    last_error = None
    while True:
        now = time.time()
        active = [c for c in candidates if _cooldown_until(*c) <= now]
        if not active:
            soonest = min(_cooldown_until(*c) for c in candidates)
            if soonest > deadline:
                break  # nothing recovers within our patience
            time.sleep(max(soonest - now, 0.2) + 0.3)
            continue
        for provider, model in active:
            text, error = _try_model(provider, model, system, user, max_tokens)
            if text:
                return text
            last_error = error
        if time.time() >= deadline:
            break
    if last_error is None:
        last_error = ("no model could be tried: every candidate is cooling down after "
                      "hitting a quota/rate limit, or the request is too large for the "
                      "ones that remain")
    raise AgentCallError(
        f"Call failed across all candidate models {candidates}: {last_error}"
    )


def _emit(on_update, event_type, payload):
    if on_update:
        on_update(event_type, payload)


def run_stage1(agent_key, ticker, data, prefer_provider=None):
    sections = "\n".join(f"- {s}" for s in STAGE1_OUTPUT_SPEC[agent_key])
    prompt = STAGE1_PROMPT_TEMPLATE.format(
        ticker=ticker,
        agent=AGENT_DISPLAY_NAMES[agent_key],
        sections=sections,
        data=data,
    )
    return _call(STAGE1_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, STAGE1_MAX_TOKENS,
                 prefer_provider=prefer_provider)


def run_stage1_all(ticker, data, agent_keys=None, on_update=None):
    """Runs the selected committee's independent first-pass analyses
    concurrently — they don't read each other's output, so there's no reason
    to serialize them. Results land in `on_update` in whatever order finishes
    first, not agent_keys order."""
    agent_keys = agent_keys or DEFAULT_AGENTS
    results = {}
    with ThreadPoolExecutor(max_workers=len(agent_keys)) as executor:
        # Alternate which provider each agent tries first, so a big roster's
        # simultaneous requests don't all hit one provider's per-minute limit.
        future_to_agent = {
            executor.submit(run_stage1, agent_key, ticker, data, "groq" if i % 2 else None): agent_key
            for i, agent_key in enumerate(agent_keys)
        }
        for future in as_completed(future_to_agent):
            agent_key = future_to_agent[future]
            text = future.result()
            results[agent_key] = text
            _emit(on_update, "stage1", {"agent": agent_key, "text": text})
    return results


def _format_transcript(turns, per_turn_limit=None, keep_recent=None):
    """per_turn_limit clips each turn's text. With keep_recent, only the turns
    older than the last `keep_recent` are clipped: late in a long debate the
    recent exchange is what an agent is answering, while the early turns only
    need their gist, and the full transcript plus a richer data block no longer
    fits Groq's request cap."""
    if not turns:
        return "(debate has not started yet)"
    older = len(turns) - keep_recent if keep_recent else None

    def clip(i, t):
        if not per_turn_limit or len(t) <= per_turn_limit:
            return t
        if older is not None and i >= older:
            return t
        return t[:per_turn_limit].rstrip() + "..."

    return "\n".join(f"{AGENT_DISPLAY_NAMES[a]}: {clip(i, t)}" for i, (a, t) in enumerate(turns))


# Each debate turn re-sends the agent's own first pass as an anchor; the full
# ~1,400-token text every turn eats Groq's per-minute token budget, and the
# anchor only needs the reasoning gist plus the Verdict at the tail.
_OWN_POSITION_CHARS = 1500
# In a debate or live chat, turns older than the last few are clipped to their
# gist so the prompt still fits Groq's cap now that the data block is richer.
_OLD_TURN_CHARS = 380
_RECENT_TURNS_FULL = 6


def run_debate_turn(agent_key, ticker, data, turns, instruction, roster, own_position=None):
    prompt = DEBATE_TURN_TEMPLATE.format(
        agent=AGENT_DISPLAY_NAMES[agent_key],
        ticker=ticker,
        data=data,
        roster=roster,
        own_position=_condense(own_position, _OWN_POSITION_CHARS) if own_position else "(not available)",
        transcript=_format_transcript(turns, per_turn_limit=_OLD_TURN_CHARS, keep_recent=_RECENT_TURNS_FULL),
        instruction=instruction,
    )
    return _call(DEBATE_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, DEBATE_MAX_TOKENS)


def run_full_debate(ticker, data, stage1, agent_keys=None, on_update=None):
    agent_keys = agent_keys or DEFAULT_AGENTS
    roster = roster_line(agent_keys)
    turn_plan = build_debate_turn_plan(agent_keys)
    turns = []
    for turn_number, agent_key, instruction in turn_plan:
        text = run_debate_turn(
            agent_key, ticker, data, turns, instruction, roster, own_position=stage1.get(agent_key)
        )
        turns.append((agent_key, text))
        _emit(on_update, "debate_turn", {"turn": turn_number, "agent": agent_key, "text": text})
    return turns


def run_cross_exam(agent_key, target_agent_key, target_statement, ticker, data, agent_keys=None):
    roster = roster_line(agent_keys or DEFAULT_AGENTS)
    prompt = CROSS_EXAM_TEMPLATE.format(
        agent=AGENT_DISPLAY_NAMES[agent_key],
        ticker=ticker,
        roster=roster,
        target_agent=AGENT_DISPLAY_NAMES[target_agent_key],
        target_statement=target_statement,
        data=data,
    )
    return _call(DEBATE_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, DEBATE_MAX_TOKENS)


def run_user_question(agent_key, ticker, data, turns, question, agent_keys=None, cio_memo=None):
    prompt = USER_QUESTION_TEMPLATE.format(
        agent=AGENT_DISPLAY_NAMES[agent_key],
        ticker=ticker,
        data=data,
        roster=roster_line(agent_keys or DEFAULT_AGENTS),
        transcript=_format_transcript(turns, per_turn_limit=_OLD_TURN_CHARS, keep_recent=_RECENT_TURNS_FULL),
        cio_memo=cio_memo or "(debate still in progress)",
        question=question,
    )
    return _call(DEBATE_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, DEBATE_MAX_TOKENS)


def run_user_question_all(ticker, data, turns, question, agent_keys=None, cio_memo=None, on_update=None):
    """Fans a single user question out to every agent on this job's committee
    concurrently — same pattern as run_stage1_all, since none of these calls
    depend on each other's answer."""
    agent_keys = agent_keys or DEFAULT_AGENTS
    results = {}
    with ThreadPoolExecutor(max_workers=len(agent_keys)) as executor:
        future_to_agent = {
            executor.submit(run_user_question, agent_key, ticker, data, turns, question, agent_keys, cio_memo):
                agent_key
            for agent_key in agent_keys
        }
        for future in as_completed(future_to_agent):
            agent_key = future_to_agent[future]
            text = future.result()
            results[agent_key] = text
            _emit(on_update, "user_answer", {"agent": agent_key, "text": text})
    return results


_VERDICT_RE = re.compile(
    r"^\s*VERDICT:\s*(BUY|HOLD|SELL)\s*\|\s*CONVICTION:\s*(\d{1,2})\s*/\s*10\s*\n+",
    re.IGNORECASE,
)


def _parse_cio_verdict(text):
    """Splits the machine-readable VERDICT/CONVICTION line the CIO prompt
    requires off the front of the memo. Falls back to (text, None, None)
    if the model didn't format it exactly right, rather than raising —
    a missing badge is a much smaller failure than losing the whole memo."""
    match = _VERDICT_RE.match(text)
    if not match:
        return text, None, None
    verdict = match.group(1).upper()
    conviction = int(match.group(2))
    return text[match.end():].lstrip(), verdict, conviction


def _condense(text, limit):
    """Keeps the head and (mostly) the tail of a first-pass analysis — the
    Verdict is always its final section, so a plain prefix cut would drop the
    one part the CIO can't do without."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.35)
    return text[:head].rstrip() + " [...] " + text[-(limit - head):].lstrip()


# Groq's free tier rejects requests over ~7.5k tokens (input + output) per
# minute, so when every Gemini model is exhausted or overloaded the full CIO
# prompt has nowhere to go. A fixed "compact" size stopped being enough once
# committees grew past nine agents (more first-passes AND more debate turns),
# so the fallback is now sized from the actual roster to fit that budget.
_CIO_FULL_PROMPT_PATIENCE = 25
_CIO_COMPACT_MAX_TOKENS = 1500
_CIO_COMPACT_DATA_CHARS = 3000
_CHARS_PER_TOKEN = 3.5  # same estimate _call() uses to decide what fits Groq


def _compact_cio_limits(system, n_agents, turns):
    """(first_pass_chars_per_agent, chars_per_debate_turn) that keep the compact
    CIO request under Groq's cap for this roster. Shrinks the debate-turn clip
    first (the transcript is the bulkier part), then each first pass."""
    from agents.prompts import CIO_PROMPT_TEMPLATE  # local: template is large

    budget = (_GROQ_MAX_REQUEST_TOKENS - _CIO_COMPACT_MAX_TOKENS) * _CHARS_PER_TOKEN
    fixed = len(system) + len(CIO_PROMPT_TEMPLATE) + _CIO_COMPACT_DATA_CHARS + 600  # + slack
    for turn_cap in (450, 340, 260):
        transcript = sum(min(len(t), turn_cap) + 25 for _, t in turns)
        per_agent = (budget - fixed - transcript) / max(n_agents, 1)
        if per_agent >= 300:
            return int(min(per_agent, 1100)), turn_cap
    return 300, 260


def run_cio(ticker, data, turns, stage1_analyses):
    system = CIO_SYSTEM_PROMPT.format(ticker=ticker)

    def build(stage1_limit=None, data_limit=None, turn_limit=None):
        stage1_text = "\n\n".join(
            f"--- {AGENT_DISPLAY_NAMES[a]} first pass ---\n"
            f"{_condense(text, stage1_limit) if stage1_limit else text}"
            for a, text in stage1_analyses.items()
        )
        return CIO_PROMPT_TEMPLATE.format(
            ticker=ticker,
            transcript=_format_transcript(turns, turn_limit),
            stage1_analyses=stage1_text,
            data=data[:data_limit] if data_limit else data,
        )

    try:
        text = _call(CIO_CANDIDATES, system, build(), CIO_MAX_TOKENS, max_wait=_CIO_FULL_PROMPT_PATIENCE)
    except AgentCallError as exc:
        stage1_limit, turn_limit = _compact_cio_limits(system, len(stage1_analyses), turns)
        log.warning("full CIO prompt failed on every model (%.200s); retrying compact "
                    "(first pass %d chars, turn %d chars)", exc, stage1_limit, turn_limit)
        text = _call(
            CIO_CANDIDATES, system,
            build(stage1_limit, _CIO_COMPACT_DATA_CHARS, turn_limit), _CIO_COMPACT_MAX_TOKENS,
        )
    return _parse_cio_verdict(text)


def run_committee(ticker, data, agent_keys=None, on_update=None):
    agent_keys = agent_keys or DEFAULT_AGENTS
    _emit(on_update, "stage_start", {"stage": "stage1"})
    stage1 = run_stage1_all(ticker, data, agent_keys=agent_keys, on_update=on_update)

    _emit(on_update, "stage_start", {"stage": "debate"})
    turns = run_full_debate(ticker, data, stage1, agent_keys=agent_keys, on_update=on_update)

    _emit(on_update, "stage_start", {"stage": "cio"})
    memo, verdict, conviction = run_cio(ticker, data, turns, stage1)
    _emit(on_update, "cio", {"text": memo, "verdict": verdict, "conviction": conviction})

    return {"stage1": stage1, "debate": turns, "cio_memo": memo, "verdict": verdict, "conviction": conviction}
