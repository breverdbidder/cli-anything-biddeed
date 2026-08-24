-- fl_appellate_watch + fl_citation_audit (issue: fork juriscraper + eyecite
-- (BSD-2) into breverdbidder, scaffold scripts/fl_appellate_watch.py)
--
-- Both tables back scripts/fl_appellate_watch.py:
--   fl_appellate_watch  -- Pass 1: party-name hits from polling FSC + all six
--                          DCAs via juriscraper (watches for "Everest Capital"
--                          in case an appeal reaches the DCAs in
--                          05-2025-CA-014890, Brevard Circuit).
--   fl_citation_audit   -- Pass 2: every citation eyecite extracts (or fails
--                          to extract -- see "malformed") from the
--                          lien-priority Academy seed corpus.
--
-- RLS ENABLED, no anon/authenticated policy on either table -- deny-all for
-- those roles, matching the deny-all-by-default pattern already used across
-- this schema (e.g. summitleads.* before its narrow anon policies were
-- added). Only service_role (which bypasses RLS) and the script's
-- SUPABASE_SERVICE_ROLE_KEY writes/reads these tables.

create table if not exists public.fl_appellate_watch (
  id uuid primary key default gen_random_uuid(),
  court text not null,
  case_name text,
  docket_number text,
  date_filed date,
  url text,
  party_match text,
  first_seen_at timestamptz not null default now(),
  raw jsonb
);

create index if not exists fl_appellate_watch_court_idx on public.fl_appellate_watch(court);
create index if not exists fl_appellate_watch_docket_idx on public.fl_appellate_watch(docket_number);

alter table public.fl_appellate_watch enable row level security;
alter table public.fl_appellate_watch force row level security;

create table if not exists public.fl_citation_audit (
  id uuid primary key default gen_random_uuid(),
  source_path text not null,
  cite_text text not null,
  cite_type text,
  resolved boolean not null default false,
  reporter text,
  volume text,
  page text,
  created_at timestamptz not null default now()
);

create index if not exists fl_citation_audit_source_path_idx on public.fl_citation_audit(source_path);
create index if not exists fl_citation_audit_resolved_idx on public.fl_citation_audit(resolved);

alter table public.fl_citation_audit enable row level security;
alter table public.fl_citation_audit force row level security;
