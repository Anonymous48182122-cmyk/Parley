# Parley

Nine legendary investor frameworks — Buffett, Munger, Lynch, Jhunjhunwala, Simons,
Ackman, plus a Historian, a Future Agent, and a Devil's Advocate — independently
analyse a stock, then debate it live, then a CIO synthesizes a memo that preserves
disagreement instead of averaging it away. Works for US (SEC EDGAR) and India
(Screener.in) tickers.

## Setup

1. `pip install -r requirements.txt`
2. `cp .env.example .env` and fill in:
   - `GEMINI_API_KEY` from https://aistudio.google.com/apikey (free, primary)
   - `GROQ_API_KEY` from https://console.groq.com/keys (free, cross-provider fallback if Gemini is overloaded/rate-limited)
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` from a free
     Supabase project's Settings → API (used for auth + saved debate history).
     Run this once in the Supabase SQL Editor:
     ```sql
     create table saved_debates (
       id uuid primary key default gen_random_uuid(),
       user_id uuid not null references auth.users(id) on delete cascade,
       ticker text not null,
       market text,
       cio_memo text,
       stage1 jsonb,
       debate jsonb,
       created_at timestamptz not null default now()
     );
     alter table saved_debates enable row level security;
     create policy "Users manage their own debates" on saved_debates
       for all using (auth.uid() = user_id);
     grant select, insert, update, delete on public.saved_debates to service_role;
     ```
3. `cd frontend && npm install && cp .env.example .env` and fill in
   `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` (same Supabase project,
   public anon key only — leave `VITE_API_BASE_URL` blank for local dev).

## Run locally

```
./dev.sh
```

This starts the FastAPI backend on `:8420` and the Vite dev server on `:5173`
(which proxies `/api/*` to the backend). Open `http://localhost:5173`.

If `dev.sh` doesn't work on your shell, run the two halves in separate terminals:

```
python -m uvicorn api.main:app --reload --port 8420
cd frontend && npm run dev
```

## Testing each layer independently

- `python test_data_layer.py` — fetches and normalizes real financials for
  Palantir (US/EDGAR) and Urban Company (India/Screener), no Claude calls.
- `python smoke_test.py` — full 9-agent + debate + CIO pipeline against
  hand-pasted AAPL data, printed to the console.
- `python run_analysis.py <TICKER> [--market US|India]` — the real thing:
  fetch live data, run the full committee, print everything.

## Architecture

```
data/us/edgar_fetcher.py       SEC EDGAR XBRL, tag-synonym fallback lists, 24hr cache
data/india/bse_fetcher.py      Screener.in HTML (price, financials, shareholding pattern)
data/common.py                 shared normalized schema + format_for_agents()
agents/prompts.py              9 agent + CIO system prompts, debate turn plan, cross-exam template
agents/runner.py               Stage 1 (first pass) -> Stage 2 (12-turn debate) -> Stage 3 (CIO)
orchestrator/analyze.py        auto-detects US vs India and routes to the right fetcher
api/main.py, api/jobs.py       FastAPI async job + polling API, 48hr analysis cache
frontend/                      Vite + React + PWA — SearchPage, live CommitteePage debate stream
```

Model allocation: everything runs on free tiers (no cost, no credit card) —
`gemini-3.5-flash` primary for all first-pass and debate calls, `gemini-2.5-pro`
primary for the single CIO synthesis call. Each stage has an ordered fallback
list spanning **two providers** (`agents/runner.py`'s `STAGE1_CANDIDATES` /
`CIO_CANDIDATES`): if a Gemini model is overloaded (503), rate-limited (429),
or deprecated for new keys (404), it falls through to the next candidate,
including Groq's `llama-3.3-70b-versatile` / `openai/gpt-oss-120b` — so a
Gemini-wide outage doesn't stall the whole run. The 9 Stage-1 analyses also
run concurrently (they don't depend on each other), which meaningfully cuts
wall-clock time; the 12 debate turns stay sequential since each one reads the
transcript so far.

## Known limitations

- **Job store is in-memory + a background thread** (`api/jobs.py`). Fine as
  long as the API process itself is long-running (see Deployment below) — an
  in-progress job is lost if that process restarts/redeploys mid-run.
- **EDGAR has no price or market cap** — only financial statement data. Agents
  that need valuation (Buffett's margin of safety, Ackman's FCF yield, Lynch's
  PEG) work off fundamentals alone for US tickers until a price source is wired
  in. Screener.in already provides price/market cap for India tickers.
- **Screener.in scraping is HTML-structure-dependent** — if Screener changes
  their page layout, `data/india/bse_fetcher.py`'s table parsing will need
  updating. It fails loudly (raises, surfaced as a job error) rather than
  silently returning wrong numbers.
- Financials cache for 24hrs, full committee analyses cache for 48hrs, both
  under `data/cache/`. `DELETE /analysis/{ticker}/cache` forces re-analysis.

## Deployment

Split across two free hosts, because the backend's background-thread pipeline
(a full committee run takes minutes) doesn't fit Vercel serverless functions'
execution time limit — Render runs it as a normal long-lived process instead:

- **Backend → Render** (free tier): "New + → Blueprint", point it at this
  repo — `render.yaml` configures the service. Paste in the 5 secret env vars
  from your local `.env` (`GEMINI_API_KEY`, `GROQ_API_KEY`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`). Free tier spins down
  after 15 min idle and cold-starts (~30-60s) on the next request.
- **Frontend → Vercel** (free tier): import the same repo — `vercel.json`
  builds `frontend/` as a static site with SPA routing. Set env vars
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_API_BASE_URL` (the
  Render URL from above).
- In Supabase, add the Vercel domain to Authentication → URL Configuration's
  redirect allow-list, or email confirmation links will redirect to
  `localhost`.
