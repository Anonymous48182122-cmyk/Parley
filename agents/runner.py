"""
Pipeline runner: Stage 1 (independent first pass) -> Stage 2 (12-turn
free-form debate, plus optional cross-examination round) -> Stage 3 (CIO
synthesis). Every stage accepts an `on_update(event_type, payload)` callback
so a caller (the API job store, or a plain CLI script) can observe progress
turn-by-turn instead of waiting for the whole run to finish.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import groq
from dotenv import load_dotenv
from google import genai
from google.genai import errors as gemini_errors
from google.genai import types

from agents.prompts import (
    AGENT_DISPLAY_NAMES,
    AGENTS,
    CIO_PROMPT_TEMPLATE,
    CIO_SYSTEM_PROMPT,
    CROSS_EXAM_TEMPLATE,
    DEBATE_TURN_PLAN,
    DEBATE_TURN_TEMPLATE,
    STAGE1_OUTPUT_SPEC,
    STAGE1_PROMPT_TEMPLATE,
    SYSTEM_PROMPTS,
)

load_dotenv()

# Two independent free-tier providers, so a Gemini-wide outage/quota wall
# doesn't stall the whole run — Groq (aistudio.google.com/apikey and
# console.groq.com, both free, no credit card) picks up the slack. Free-tier
# model availability is genuinely unstable day to day (a model free today
# gets deprecated for new keys, or is simply overloaded), so each stage tries
# an ordered (provider, model) candidate list, falling through on
# "unavailable" (404) or a model staying overloaded (503/429) after retries.
STAGE1_CANDIDATES = [
    ("gemini", "gemini-3.5-flash"),
    ("gemini", "gemini-3-flash-preview"),
    ("groq", "llama-3.3-70b-versatile"),
    ("gemini", "gemini-3.1-flash-lite"),
    ("groq", "openai/gpt-oss-120b"),
]
DEBATE_CANDIDATES = STAGE1_CANDIDATES
CIO_CANDIDATES = [
    ("gemini", "gemini-2.5-pro"),
    ("groq", "llama-3.3-70b-versatile"),
    ("gemini", "gemini-3-flash-preview"),
    ("groq", "openai/gpt-oss-120b"),
    ("gemini", "gemini-3.1-flash-lite"),
]

STAGE1_MAX_TOKENS = 1400
DEBATE_MAX_TOKENS = 300
CIO_MAX_TOKENS = 2500

_MAX_RETRIES_PER_MODEL = 3

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
            _gemini_client = genai.Client(api_key=api_key)
        return _gemini_client


def _get_groq_client():
    global _groq_client
    with _client_lock:
        if _groq_client is None:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise AgentCallError("GROQ_API_KEY is not set in the environment")
            _groq_client = groq.Groq(api_key=api_key)
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
    response = _get_groq_client().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


_GEMINI_RETRYABLE = (gemini_errors.ServerError,)
_GROQ_RETRYABLE = (groq.RateLimitError, groq.InternalServerError, groq.APIConnectionError, groq.APITimeoutError)


def _is_retryable(provider, exc):
    if provider == "gemini":
        if isinstance(exc, _GEMINI_RETRYABLE):
            return True
        return isinstance(exc, gemini_errors.ClientError) and exc.code == 429
    return isinstance(exc, _GROQ_RETRYABLE)


def _retry_delay(attempt):
    return min(30, 2**attempt)


def _call(candidates, system, user, max_tokens):
    if isinstance(candidates, tuple):
        candidates = [candidates]

    last_error = None
    for provider, model in candidates:
        for attempt in range(_MAX_RETRIES_PER_MODEL):
            try:
                text = _call_gemini(model, system, user, max_tokens) if provider == "gemini" \
                    else _call_groq(model, system, user, max_tokens)
                if not text:
                    last_error = f"{provider}:{model} returned no text (likely a safety-filter block)"
                    break  # try next candidate
                return text.strip()
            except Exception as exc:  # noqa: BLE001 — deliberately broad, see module docstring
                last_error = exc
                if _is_retryable(provider, exc):
                    time.sleep(_retry_delay(attempt))
                    continue
                break  # model/provider unavailable or a non-retryable error — try next candidate
    raise AgentCallError(
        f"Call failed across all candidate models {candidates}: {last_error}"
    )


def _emit(on_update, event_type, payload):
    if on_update:
        on_update(event_type, payload)


def run_stage1(agent_key, ticker, data):
    sections = "\n".join(f"- {s}" for s in STAGE1_OUTPUT_SPEC[agent_key])
    prompt = STAGE1_PROMPT_TEMPLATE.format(
        ticker=ticker,
        agent=AGENT_DISPLAY_NAMES[agent_key],
        sections=sections,
        data=data,
    )
    return _call(STAGE1_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, STAGE1_MAX_TOKENS)


def run_stage1_all(ticker, data, on_update=None):
    """Runs all 9 independent first-pass analyses concurrently — they don't
    read each other's output, so there's no reason to serialize them. Results
    land in `on_update` in whatever order finishes first, not AGENTS order."""
    results = {}
    with ThreadPoolExecutor(max_workers=len(AGENTS)) as executor:
        future_to_agent = {
            executor.submit(run_stage1, agent_key, ticker, data): agent_key for agent_key in AGENTS
        }
        for future in as_completed(future_to_agent):
            agent_key = future_to_agent[future]
            text = future.result()
            results[agent_key] = text
            _emit(on_update, "stage1", {"agent": agent_key, "text": text})
    return results


def _format_transcript(turns):
    if not turns:
        return "(debate has not started yet)"
    return "\n".join(f"{AGENT_DISPLAY_NAMES[a]}: {t}" for a, t in turns)


def run_debate_turn(agent_key, ticker, data, turns, instruction):
    prompt = DEBATE_TURN_TEMPLATE.format(
        agent=AGENT_DISPLAY_NAMES[agent_key],
        ticker=ticker,
        data=data,
        transcript=_format_transcript(turns),
        instruction=instruction,
    )
    return _call(DEBATE_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, DEBATE_MAX_TOKENS)


def run_full_debate(ticker, data, on_update=None):
    turns = []
    for turn_number, agent_key, instruction in DEBATE_TURN_PLAN:
        text = run_debate_turn(agent_key, ticker, data, turns, instruction)
        turns.append((agent_key, text))
        _emit(on_update, "debate_turn", {"turn": turn_number, "agent": agent_key, "text": text})
    return turns


def run_cross_exam(agent_key, target_agent_key, target_statement, ticker, data):
    prompt = CROSS_EXAM_TEMPLATE.format(
        agent=AGENT_DISPLAY_NAMES[agent_key],
        ticker=ticker,
        target_agent=AGENT_DISPLAY_NAMES[target_agent_key],
        target_statement=target_statement,
        data=data,
    )
    return _call(DEBATE_CANDIDATES, SYSTEM_PROMPTS[agent_key], prompt, DEBATE_MAX_TOKENS)


def run_cio(ticker, data, turns, stage1_analyses):
    system = CIO_SYSTEM_PROMPT.format(ticker=ticker)
    stage1_text = "\n\n".join(
        f"--- {AGENT_DISPLAY_NAMES[a]} first pass ---\n{text}"
        for a, text in stage1_analyses.items()
    )
    prompt = CIO_PROMPT_TEMPLATE.format(
        ticker=ticker,
        transcript=_format_transcript(turns),
        stage1_analyses=stage1_text,
        data=data,
    )
    return _call(CIO_CANDIDATES, system, prompt, CIO_MAX_TOKENS)


def run_committee(ticker, data, on_update=None):
    _emit(on_update, "stage_start", {"stage": "stage1"})
    stage1 = run_stage1_all(ticker, data, on_update=on_update)

    _emit(on_update, "stage_start", {"stage": "debate"})
    turns = run_full_debate(ticker, data, on_update=on_update)

    _emit(on_update, "stage_start", {"stage": "cio"})
    memo = run_cio(ticker, data, turns, stage1)
    _emit(on_update, "cio", {"text": memo})

    return {"stage1": stage1, "debate": turns, "cio_memo": memo}
