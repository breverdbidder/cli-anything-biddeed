-- Issue #19600: Canopy Connect completion (client-side /api/canopy-complete
-- and server-side /api/canopy-webhook) both upsert protection_partners_intake
-- rows keyed by Canopy's pull_id, so either callback can create the row and
-- the other can safely update it without creating a duplicate lead. Additive
-- only -- no existing column touched, per CC_META_PROMPT.md 3.4.
alter table public.protection_partners_intake
  add column if not exists pull_id text;

create unique index if not exists protection_partners_intake_pull_id_key
  on public.protection_partners_intake (pull_id)
  where pull_id is not null;
