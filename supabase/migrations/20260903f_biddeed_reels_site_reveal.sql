-- CMO Factory CP3d (issue #19785) -- "site reveal" bolt32 segment tracking
-- columns. Additive only, per M2/M5 -- no existing column dropped or
-- retyped, no row touched by this migration itself.
--
-- winnerdata.biddeed_reels gains 3 columns per the issue's literal list:
-- page_capture_url, page_http_status, capture_ms. These record what
-- scripts/reel_site_reveal.py observed when it captured the real deal page
-- for the site-reveal beat (24.0-28.0s) -- never invented, never a mockup.
--
-- NOT APPLIED LIVE THIS SESSION: this repo's documented migration-apply
-- path for winnerdata (winnerdata is not PostgREST-exposed on this
-- project, confirmed again this session -- see 20260903e's own comment
-- block) is either `supabase db push` with a linked project (no `supabase`
-- CLI binary present in this sandbox) or SSH to the Hetzner box per
-- .github/workflows/apply-summit-verifications-migration.yml (HETZNER_SSH_KEY
-- was present in env, but outbound port 22 to 87.99.129.125 timed out from
-- this sandbox's network egress -- tested live, not assumed). Direct psql
-- to the pooler also fails per the long-standing documented constraint
-- (decision_log 169/205/287). This migration file is the deliverable per
-- M6/the Supabase CLI workflow's own step 5 ("commit the migration file to
-- repo"); applying it is CI/runner work, not reachable from this session.

begin;

alter table winnerdata.biddeed_reels
  add column if not exists page_capture_url text,
  add column if not exists page_http_status integer,
  add column if not exists capture_ms integer;

comment on column winnerdata.biddeed_reels.page_capture_url is
  'The exact URL scripts/reel_site_reveal.py navigated to for the site-reveal beat capture, including the ?reel=1 flag. Null for rows never captured.';

comment on column winnerdata.biddeed_reels.page_http_status is
  'HTTP status Playwright observed on page_capture_url. >=400 or null means the site-reveal capture FAILED QA (issue #19785 guard rail) -- the reel must not ship with a QR/inset pointing at this page.';

comment on column winnerdata.biddeed_reels.capture_ms is
  'Wall-clock milliseconds the Playwright capture took (page load + screenshot + scroll capture), for the CI/runner-memory guard from the #19785 re-dispatch comment (one page at a time, PID-safe per docs/intent/19678.md).';

commit;
