-- WinnerData seller_digest lead persistence + enrichment pipeline (issue #19619).
--
-- Root cause fixed here: winnerdata_daily_winner_ff_digest.py only wrote the
-- COUNT of leads into ff_batches.lead_count -- the actual lead rows were never
-- persisted anywhere. This migration adds the storage and enrichment columns
-- so the build script can actually write them, and the new enrichment + PDF
-- render scripts can consume them before Ariel approves.
--
-- Design decision: new table winnerdata.seller_digest_leads (not reusing
-- winnerdata.ff_batch_leads) because:
--   1. ff_batch_leads.auction_id FK references public.multi_county_auctions(id)
--      -- seller_digest leads come from winnerdata.leads, keyed by lead_id.
--   2. ff_batch_leads enforces tier1_buyer_type = 'third_party'; seller_digest
--      leads are insurance prospects, not auction third-party buyers.
--   3. The PK (batch_date, auction_id) is wrong for this data shape.
--   A separate table makes the FK contract clean and lets ff_batch_leads stay
--   unmodified for the nine_case_portfolio flow (guardrail from issue).
--
-- ff_batches enrichment columns: additive. A seller_digest batch now has the
-- same enrichment_status lifecycle as a nine_case_portfolio batch -- the UI
-- and alerting already watch this column.

begin;

-- ── 1. Enrichment columns on ff_batches ──────────────────────────────────────
-- These already exist on nine_case_portfolio rows (added by earlier migrations)
-- but only the nine-case enrichment script ever set them. Adding them here via
-- add column if not exists is safe/idempotent.

alter table winnerdata.ff_batches
  add column if not exists enrichment_status text not null default 'not_started'
  check (enrichment_status in ('not_started','running','complete','failed'));

alter table winnerdata.ff_batches
  add column if not exists enrichment_run_id text;

alter table winnerdata.ff_batches
  add column if not exists enrichment_started_at timestamptz;

alter table winnerdata.ff_batches
  add column if not exists enrichment_completed_at timestamptz;

alter table winnerdata.ff_batches
  add column if not exists enrichment_error text;

alter table winnerdata.ff_batches
  add column if not exists pdf_render_status text not null default 'not_started'
  check (pdf_render_status in ('not_started','running','complete','failed'));

alter table winnerdata.ff_batches
  add column if not exists pdf_render_completed_at timestamptz;

alter table winnerdata.ff_batches
  add column if not exists pdf_artifact_url text;

-- ── 2. seller_digest_leads table ─────────────────────────────────────────────
-- Keyed (batch_date, lead_id). Populated by the build step immediately after
-- computing lead_count; consumed by the enrichment + PDF render steps before
-- Ariel approves.

create table if not exists winnerdata.seller_digest_leads (
  batch_date     date     not null references winnerdata.ff_batches(batch_date) on delete cascade,
  lead_id        uuid     not null references winnerdata.leads(lead_id),

  -- From get_batch_leads() join (signal_events + routing_decisions)
  entity_name    text,
  county         text,
  sale_type      text,
  case_number    text,
  sold_amount    numeric,
  property_address text,
  routed_at      timestamptz,

  -- Contact tier from consent_certificate (raw tier string, e.g. "2:tracerfy_enhanced_trace")
  email_tier     text,
  phone_tier     text,

  -- Enrichment fields (populated by seller_digest_enrichment.py)
  phone          text,
  email          text,
  contact_provider text,
  contact_verified_at timestamptz,
  is_dnc         boolean,
  dnc_checked_at timestamptz,
  dnc_provider   text,

  -- QA / provenance
  row_enrichment_status text not null default 'not_started'
    check (row_enrichment_status in ('not_started','running','complete','failed','skipped_dnc_incomplete')),
  evidence_ledger jsonb not null default '{}'::jsonb,
  unresolved_field_count integer not null default 0,

  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  primary key (batch_date, lead_id)
);

create index if not exists seller_digest_leads_date_idx
  on winnerdata.seller_digest_leads(batch_date);

comment on table winnerdata.seller_digest_leads is
  'Persisted lead rows for batch_kind=seller_digest ff_batches. '
  'The build step (winnerdata_daily_winner_ff_digest.py) inserts one row per '
  'lead returned by get_batch_leads() for the batch_date. '
  'Enrichment (scripts/seller_digest_enrichment.py) populates phone/email/is_dnc '
  'BEFORE Ariel approves. PDF render happens after enrichment, before approval. '
  'See issue #19619.';

commit;
