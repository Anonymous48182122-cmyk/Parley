"""
FastAPI backend: async job + polling pattern. POST /analyze kicks off (or
returns cached) analysis; GET /analysis/{ticker} polls live progress;
GET /analysis/{ticker}/summary returns the light CIO-memo-only payload;
DELETE /analysis/{ticker}/cache forces re-analysis next time.
"""

import threading
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.prompts import AGENT_DISPLAY_NAMES, AGENTS
from agents.runner import AgentCallError, run_cross_exam
from backend import jobs
from backend.history import router as history_router
from data.search import search_tickers

app = FastAPI(title="Parley API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history_router)


@app.on_event("startup")
def _warm_search_cache():
    """Loads and caches the ~10k US + ~2k India ticker lists in the background
    on process start, so the first real user's search isn't the one paying
    for that fetch — matters most right after a cold start (e.g. Render's
    free tier waking up from idle)."""
    def warm():
        try:
            search_tickers("a", limit=1)
        except Exception:
            pass  # best-effort — a real search request will just retry the fetch

    threading.Thread(target=warm, daemon=True).start()


class AnalyzeRequest(BaseModel):
    ticker: str
    market: Optional[str] = None  # "US" | "India" | None (auto-detect)


class CrossExamRequest(BaseModel):
    agent: str
    target_agent: str
    target_statement: str


def _job_response(job):
    return {
        "ticker": job["ticker"],
        "market": job["market"],
        "status": job["status"],
        "current_stage": job.get("current_stage"),
        "progress": jobs.progress_fraction(job),
        "stage1": job["stage1"],
        "debate": job["debate"],
        "cio_memo": job.get("cio_memo"),
        "error": job.get("error"),
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/agents")
def list_agents():
    return [{"key": key, "name": AGENT_DISPLAY_NAMES[key]} for key in AGENTS]


@app.get("/search")
def search(q: str = ""):
    return search_tickers(q, limit=8)


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not req.ticker or not req.ticker.strip():
        raise HTTPException(400, "ticker is required")
    job = jobs.start_analysis(req.ticker.strip(), market=req.market)
    return _job_response(job)


@app.get("/analysis/{ticker}")
def get_analysis(ticker: str):
    job = jobs.get_job(ticker)
    if not job:
        raise HTTPException(404, "No analysis found for this ticker. POST /analyze first.")
    return _job_response(job)


@app.get("/analysis/{ticker}/summary")
def get_summary(ticker: str):
    job = jobs.get_job(ticker)
    if not job:
        raise HTTPException(404, "No analysis found for this ticker. POST /analyze first.")
    return {
        "ticker": job["ticker"],
        "status": job["status"],
        "cio_memo": job.get("cio_memo"),
        "error": job.get("error"),
    }


@app.delete("/analysis/{ticker}/cache")
def delete_cache(ticker: str):
    jobs.clear_cache(ticker)
    return {"cleared": True}


@app.post("/analysis/{ticker}/cross-exam")
def cross_exam(ticker: str, req: CrossExamRequest):
    job = jobs.get_job(ticker)
    if not job or not job.get("data_text"):
        raise HTTPException(404, "Run analysis for this ticker first.")
    if req.agent not in AGENTS or req.target_agent not in AGENTS:
        raise HTTPException(400, "Unknown agent key.")
    try:
        text = run_cross_exam(req.agent, req.target_agent, req.target_statement, ticker, job["data_text"])
    except AgentCallError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"agent": req.agent, "text": text}
