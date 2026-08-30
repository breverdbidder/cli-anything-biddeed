-- Issue #19602 Task 1: private Supabase Storage bucket for the dec-page
-- upload fallback intake path (functions/api/dec-upload.ts).
--
-- No new columns on public.protection_partners_intake are needed for this
-- feature -- the file reference (storage_bucket/storage_path/file_name/
-- file_type/file_size) lives inside the existing `payload jsonb` column,
-- same pattern as applicant/property/quote_request in functions/api/quote.ts.
-- This migration's only job is the storage bucket itself.
--
-- Same access posture as the table: RLS is on for storage.objects by
-- default with zero policies added here, so anon/authenticated get no
-- access at all. functions/api/dec-upload.ts writes with
-- SUPABASE_SERVICE_ROLE, which bypasses RLS -- the only write path, same
-- discipline as protection_partners_intake itself.
--
-- APPLIED LIVE via the Supabase Storage REST API
-- (POST {SUPABASE_URL}/storage/v1/bucket with the service-role key), not
-- direct SQL -- same known constraint as every prior migration in this repo
-- (no exec_sql/DDL RPC reachable, direct psql auth fails in this
-- environment; see decision_log ids 169/205/287). The Storage API is also
-- the officially supported way to create a bucket, so this is not a
-- workaround, it's the correct interface. This INSERT is kept as the
-- idempotent source-of-truth record of what was created; the bucket already
-- exists live as of 2026-08-30T04:27:04Z (verified via GET
-- /storage/v1/bucket/protection-partners-dec-uploads returning the row
-- below). Re-running this INSERT is a no-op via ON CONFLICT if a psql/DDL
-- path ever becomes available.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'protection-partners-dec-uploads',
  'protection-partners-dec-uploads',
  false,
  10485760,
  array['application/pdf', 'image/jpeg', 'image/png']
)
on conflict (id) do nothing;
