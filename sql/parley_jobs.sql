-- Durable copy of each analysis, so a server restart does not lose a run that someone is reading.
-- Run this once in the Supabase SQL editor. The backend uses the service role key, which bypasses row
-- level security, so no policies are added: with security on and no policies, nobody else can read it.

create table if not exists public.parley_jobs (
  ticker     text primary key,
  job        jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.parley_jobs enable row level security;

create index if not exists parley_jobs_updated_at on public.parley_jobs (updated_at);
