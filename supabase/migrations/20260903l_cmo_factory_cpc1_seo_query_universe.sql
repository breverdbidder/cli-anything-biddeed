-- CMO Factory CP-C1 (issue #19821): SEO/AEO/GEO query universe.
-- content_library's shape (auction_date, content_id, platform, type, content
-- jsonb -- see app definitions) is a social-post queue, not a keyword table:
-- no query_text/cluster/intent/difficulty columns and its required fields
-- (auction_date, content_id, platform) don't apply to a keyword row. New
-- table instead, per the issue's own fallback instruction.
create table if not exists public.seo_query_universe (
  id uuid primary key default gen_random_uuid(),
  query_text text not null,
  county_slug text,                      -- null for state-wide/non-county queries
  query_type text not null,               -- foreclosure_auction | tax_deed_sale | auction_calendar | how_to_bid | surplus_funds | informational_other
  intent text not null check (intent in ('informational', 'navigational', 'transactional')),
  difficulty_estimate text not null check (difficulty_estimate in ('low', 'medium', 'high')),
  difficulty_method text not null,        -- how the estimate was derived (heuristic, spot-checked, etc.)
  source text not null,                   -- generated_template | authored_informational
  target_page text,                       -- intended landing page for this query
  created_at timestamptz not null default now()
);

comment on table public.seo_query_universe is
  'CMO Factory CP-C1 (#19821): clustered SEO/AEO/GEO query universe -- 67 counties x 5 intent templates plus authored informational queries. difficulty_estimate is a heuristic (query specificity + intent), not a live SERP-tool pull -- no keyword-difficulty API was available this session; see difficulty_method per row.';

alter table public.seo_query_universe enable row level security;

-- Internal content-planning table: no anon policy. Read via service role
-- (CI/content pipeline) only, matching the M2 rule of no anon access on new
-- tables/views.
create policy seo_query_universe_service_role_all
  on public.seo_query_universe
  for all
  to service_role
  using (true)
  with check (true);

create index if not exists idx_seo_query_universe_county on public.seo_query_universe(county_slug);
create index if not exists idx_seo_query_universe_intent on public.seo_query_universe(intent);
