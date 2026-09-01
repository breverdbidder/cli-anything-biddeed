-- Same-day security follow-up to 20260901_winnerdata_lms_v1.sql.
--
-- 20260901_winnerdata_lms_v1.sql granted EXECUTE on all seven lms_* RPCs to
-- `anon`, mirroring workers/winnerdata-ff's existing pattern. That pattern
-- relies on the anon key not being a meaningful secret (Supabase's anon key
-- is designed to be embeddable client-side) plus in-function org_id scoping
-- as the real boundary. For this LMS that assumption broke in practice:
-- cli-anything-biddeed is a PUBLIC repo, the Worker source (now fixed, see
-- workers/winnerdata-lms/src/index.js) committed the literal anon key, and
-- winnerdata.organizations.org_id for the only org on file
-- ('032f4717-545f-4a18-b48b-28ea4257699d') is also committed in multiple
-- files. Combined, that meant anyone on the internet could call
-- POST https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1/rpc/lms_leads_list
-- (or lms_flag_lead / lms_update_producer_note) directly with the public
-- anon key and org_id, reading lead contact PII and billing data and writing
-- unaudited-by-a-real-actor flag/note rows -- entirely bypassing this
-- Worker's HTTP Basic Auth gate.
--
-- Fix: revoke `anon` EXECUTE on all seven functions. `service_role` and
-- `postgres` keep EXECUTE (unaffected by this migration -- they were never
-- revoked). The Worker now calls these RPCs with SUPABASE_SERVICE_KEY, a
-- real secret set via `wrangler secret put` and never committed to source
-- (see workers/winnerdata-lms/wrangler.toml). Applied live via Supabase
-- Management API 2026-09-01 before this file was written; this migration
-- makes that live change idempotent and reproducible in any other
-- environment.

begin;

revoke execute on function public.lms_orgs_list() from anon;
revoke execute on function public.lms_org_detail(uuid) from anon;
revoke execute on function public.lms_leads_list(uuid, uuid, text, date, date, integer, integer) from anon;
revoke execute on function public.lms_producer_performance(uuid) from anon;
revoke execute on function public.lms_billing_view(uuid, text) from anon;
revoke execute on function public.lms_flag_lead(uuid, uuid, text, text) from anon;
revoke execute on function public.lms_update_producer_note(uuid, uuid, text, text) from anon;

commit;
