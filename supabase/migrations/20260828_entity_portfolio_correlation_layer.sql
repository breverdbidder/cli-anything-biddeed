-- Elementix-parity entity/portfolio correlation layer for Daily Winner FFs.
-- Additive only: no existing column/table is altered or dropped.
--
-- Context: winnerdata.owner_portfolio (20260825_owner_portfolio.sql) already
-- enumerates a resolved owner's held book, but only for the batch that
-- scripts/skiptrace_20260825_portfolio_batch.py was hand-run against
-- (batch_id='20260825_third_party_portfolio', 15 rows). Every later batch's
-- portfolio_property_count in winnerdata.ff_batch_leads reads 0/NULL as a
-- result -- see portfolio_fact_finder_render.py's "UNRESOLVED -- no
-- owner_portfolio coverage on file for this entity yet (batch-scoped table,
-- not a live statewide scan)" note, and confirmed live 2026-08-28 for the
-- current 2026-08-26 highlands batch (OK Business LLC / Mundi Marketing LLC
-- both render as unresolved despite having real, resolvable multi-case
-- history in public.auction_buyer_sightings).
--
-- This migration:
--   1. Adds a source + confidence_tier pair to owner_portfolio so every row
--      inserted by scripts/entity_portfolio_resolver.py (statewide,
--      reusable, not batch-hardcoded) is self-describing per the FF
--      confidence-tier standard, matching how contact fields are already
--      tagged (VERIFIED-PRIMARY / VERIFIED-CROSS-CHECKED / LIKELY-SINGLE-
--      SOURCE / UNCONFIRMED / NOT AVAILABLE -- see
--      scripts/render_ff_9buyer_20260827.py's tier_label()).
--   2. Adds the acquisition-velocity + confidence-summary KPI fields to
--      ff_batch_leads that scripts/entity_portfolio_resolver.py computes
--      but that build_ff_portfolio_batch() has nowhere to persist today.
--   3. Ships winnerdata.build_entity_portfolio_edge() as a thin insert
--      helper so scripts/entity_portfolio_resolver.py's Python-computed
--      rows have one narrow, auditable write path into owner_portfolio
--      instead of ad hoc raw INSERTs per caller.
--
-- Not applied against the live project from this session: the Management
-- API (api.supabase.com) returned Cloudflare error 1010 (browser/IP
-- signature block) on most attempts from this sandbox, and winnerdata is
-- not in this project's PostgREST-exposed-schema list (confirmed live:
-- "Only the following schemas are exposed: public, graphql_public,
-- pascal"), so there is no reachable write path to winnerdata.* from this
-- session's environment. A handful of mgmt_sql() calls DID succeed
-- (intermittently, not a hard block -- see entity_portfolio_resolver.py's
-- reachable_backends() docstring), which is how the owner_portfolio row
-- count (15) and ff_batches/ff_batch_leads schemas above were verified
-- live. Apply this migration the same way every other 2026-08-2x migration
-- in this repo was applied: from cc-runner-ghonly.yml, where the Management
-- API is reachable per this repo's own established pattern.

begin;

alter table winnerdata.owner_portfolio
  add column if not exists source text not null default 'zw_parcels'
    check (source in ('zw_parcels', 'auction_buyer_sightings', 'sunbiz_entities')),
  add column if not exists confidence_tier text not null default 'VERIFIED-PRIMARY'
    check (confidence_tier in ('VERIFIED-PRIMARY', 'VERIFIED-CROSS-CHECKED', 'LIKELY-SINGLE-SOURCE', 'UNCONFIRMED', 'NOT AVAILABLE'));

alter table winnerdata.ff_batch_leads
  add column if not exists portfolio_acquisition_velocity_per_year numeric,
  add column if not exists portfolio_wins_on_file integer,
  add column if not exists portfolio_confidence_summary jsonb not null default '{}'::jsonb;

comment on column winnerdata.owner_portfolio.source is
  'Which correlation source produced this row: zw_parcels (statewide own_name walk), auction_buyer_sightings (cross-county buyer graph -- the source added 2026-08-28 to close the Elementix-gap), or sunbiz_entities (officer/registered-agent piercing).';
comment on column winnerdata.owner_portfolio.confidence_tier is
  'FF confidence-tier standard applied to this entity-graph edge, same vocabulary as contact-field tiers.';
comment on column winnerdata.ff_batch_leads.portfolio_acquisition_velocity_per_year is
  'Wins-per-year rate computed from public.auction_buyer_sightings.auction_date span for this buyer. NULL when fewer than 2 wins are on file (insufficient history to rate, not zero).';

create or replace function winnerdata.upsert_entity_portfolio_edge(
  p_owner_key text, p_entity_name_raw text, p_county text, p_co_no integer, p_parcel_id text,
  p_address text, p_dor_uc text, p_no_buldng integer, p_jv numeric,
  p_acquisition_source text, p_linked_via text, p_linked_via_detail text,
  p_batch_id text, p_case_number text, p_source text, p_confidence_tier text
) returns void
language sql
security definer
set search_path = winnerdata
as $$
  insert into winnerdata.owner_portfolio
    (owner_key, entity_name_raw, county, co_no, parcel_id, address, dor_uc, no_buldng, jv,
     acquisition_source, linked_via, linked_via_detail, batch_id, case_number, source, confidence_tier)
  values
    (p_owner_key, p_entity_name_raw, p_county, p_co_no, p_parcel_id, p_address, p_dor_uc, p_no_buldng, p_jv,
     p_acquisition_source, p_linked_via, p_linked_via_detail, p_batch_id, p_case_number, p_source, p_confidence_tier)
  on conflict (owner_key, co_no, parcel_id) do update set
    source = excluded.source, confidence_tier = excluded.confidence_tier,
    linked_via = excluded.linked_via, linked_via_detail = excluded.linked_via_detail;
$$;

revoke all on function winnerdata.upsert_entity_portfolio_edge(text,text,text,integer,text,text,text,integer,numeric,text,text,text,text,text,text,text) from public;
grant execute on function winnerdata.upsert_entity_portfolio_edge(text,text,text,integer,text,text,text,integer,numeric,text,text,text,text,text,text,text) to service_role;

commit;
