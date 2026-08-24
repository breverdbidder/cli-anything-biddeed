-- Protection Partners v1 website: FF quote intake table (issue #19405).
--
-- Lives in `public` (not `summitleads`/`winnerdata`) so the Cloudflare Pages
-- Function can write via the standard @supabase/supabase-js PostgREST client
-- with the service-role key -- PostgREST does not expose the `summitleads`
-- schema (see docs/winnerdata/FF_TO_MOMENTUM_MAPPING.md), and this table is a
-- distinct website-intake source, not part of the SummitLeads/Winner Data
-- auction pipeline this repo also ships.
--
-- RLS is ON with zero policies: anon/authenticated can neither read nor write
-- this table. The Cloudflare Function uses SUPABASE_SERVICE_ROLE, which
-- bypasses RLS entirely -- it is the only write path, per the issue spec.

create table if not exists public.protection_partners_intake (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  payload jsonb not null,
  consent jsonb not null,
  source text not null default 'website',
  status text not null default 'new'
);

comment on table public.protection_partners_intake is
  'Protection Partners website Get-a-Quote FF submissions. Written exclusively by functions/api/quote.ts (Cloudflare Pages Function, service-role key). See sites/protectionpartners-web/README.md.';

alter table public.protection_partners_intake enable row level security;

create index if not exists protection_partners_intake_created_at_idx
  on public.protection_partners_intake (created_at desc);

create index if not exists protection_partners_intake_status_idx
  on public.protection_partners_intake (status);
