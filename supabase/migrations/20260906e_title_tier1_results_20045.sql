-- Issue #20045 — SIGNAL$ section 16 Title Tier 1 (lien search).
--
-- Stores the raw per-case recorded-instrument list pulled from a county's
-- AcclaimWeb Official Records case-number search, keyed on mca_id
-- (multi_county_auctions.id) so the report composer reads a cached result
-- on render instead of re-scraping the clerk's site on every request (issue
-- text: "so the report reads, never re-scrapes on render").
--
-- This is deliberately broader than public.lien_results: lien_results only
-- keeps documents that regex-matched a lien-type pattern (mortgage/HOA/
-- mechanic's/UCC/tax) for Tier 2 survival classification. Title Tier 1 is
-- the full recorded-instrument list for the case (every doc type, including
-- the case's own Lis Pendens/Judgment and any satisfaction/release), which
-- is what the DoD's rendered table shows.
create table if not exists public.title_tier1_results (
  id                  bigint generated always as identity primary key,
  mca_id              uuid not null references public.multi_county_auctions(id),
  case_number         text not null,
  county              text not null,
  parcel_id           text,
  instrument_type     text,
  recording_date      date,
  book_page           text,
  instrument_number   text,
  transaction_item_id text,
  direct_name         text,
  indirect_name       text,
  amount              numeric,
  status              text not null default 'open',
  source              text not null,
  raw_data            jsonb,
  fetched_at          timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  unique (mca_id, transaction_item_id)
);

create index if not exists title_tier1_results_mca_id_idx on public.title_tier1_results (mca_id);
create index if not exists title_tier1_results_case_number_idx on public.title_tier1_results (case_number);

-- RLS enabled, no anon/authenticated policy (M2) — service_role only, same
-- pattern as lien_results/title_defects. Reads happen through the report
-- composer's service-role Supabase client (packages/biddeed-mcp/src/supabase.js),
-- not directly from a browser session.
alter table public.title_tier1_results enable row level security;
