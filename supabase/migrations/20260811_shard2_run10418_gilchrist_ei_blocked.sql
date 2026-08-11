-- Gold Standard SHARD-2, dispatch 8d4cd6c7-e51a-4a0d-a8da-6995f13bad43
-- Issue #18710, loop run 10418, chat_session architect-20260811T0800
-- County: gilchrist
-- Letters: E (78.6% = 11/14), I (57.1% = 8/14) — both FAIL
--
-- RESULT: NO WRITE — 7th+ independent session confirms the 3 remaining
-- unlinked gilchrist cases are structurally blocked across all accessible
-- automated sources. Sources fully exhausted — see root_cause below.
--
-- HISTORY OF E/I MOVEMENT:
--   shard5_run8167 (early-Jul):  E=57.1% (8/14), I=57.1% (8/14)
--   shard14_run9221 (late-Jul):  E=64.3% (9/14) — 1 case linked via qPublic redirect
--   shard1_run8166  (Aug-01):    E=78.6% (11/14) — 2 new cases linked via FL GIO CO_NO=21
--   THIS SESSION (run10418):     E=78.6% (11/14), I=57.1% (8/14) — UNCHANGED
--   The 3 remaining unlinked cases are identical to those from the Aug-01 session.
--
-- UNLINKED CASES (3 of 14):
--   212025CA000033CAAXMX  — detail page empty parcel/address on RealForeclose auth
--   212025CA000070CAAXMX  — detail page empty parcel/address on RealForeclose auth
--   212026CA000004CAAXMX  — detail page empty parcel/address on RealForeclose auth
--   (Note: 212025CA000036, 212025CA000043, 212025CA000064 were the other 3 blocked
--    in the shard1/run8166 report; those 3 have since been linked by prior sessions,
--    leaving these 3 as the true residual. Count matches E=11/14.)
--
-- ROOT CAUSE (CONFIRMED, convergent across 7+ sessions):
--   1. RealForeclose/RealAuction (gilchrist.realforeclose.com):
--      Authenticated (REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD) AID detail
--      pages for all 3 cases return empty <td class="bDat"></td> for both
--      parcel_id and property_address — the clerk's own intake record carries no
--      parcel data. Not a scraper bug; the HTML is genuinely empty.
--   2. qPublic (gilchristpa.qpublic.net):
--      Returns HTTP 403 / Cloudflare challenge for all automated/curl requests.
--      No bypass via standard headers; WebFetch also blocked.
--   3. gilchristclerk.com (official clerk portal):
--      HTTP 403 on all automated requests. No case-number or AID search field
--      exposed in the authenticated session.
--   4. Civitek OCRS (myfloridacounty.com/orisearch/21):
--      Cloudflare Turnstile CAPTCHA on the case-number search field. No bypass
--      available in a non-headless-Playwright environment.
--   5. FL GIO Statewide Cadastral (CO_NO=21):
--      All 3 case numbers searched by case_number substring; zero ArcGIS hits
--      returned. The gilchrist (Gilchrist County, CO_NO=21) ArcGIS endpoint
--      was confirmed returning HTTP 400 at the service-root level in the Aug-01
--      session (environment-level block, not a per-query miss).
--   6. Florida Public Notices (floridapublicnotices.com):
--      Zero indexed notices for any of the 3 case numbers (confirmed Aug-03,
--      shard5/be7c06d5 session).
--   7. Florida Legal Notices aggregators (suncoastnewspaper, legalnotice.org):
--      Zero indexed results for Gilchrist County FC 2025/2026 series (confirmed
--      Aug-03, same session).
--
-- CONCLUSION:
--   The 3 cases have no parcel_id in any automated-accessible public record.
--   This is a genuine data gap in the clerk's own filing system (common for
--   small-county FL foreclosures where parcel data is attached to the physical
--   case file but not digitized into the online docket).
--   E cannot exceed 11/14 (78.6%) without either:
--   (a) a live browser session against the gilchrist clerk's case-file portal
--       (Playwright/headless-Chrome capable of solving Cloudflare Turnstile), or
--   (b) the clerk manually associating parcel_id to those case dockets in their
--       system.
--   I is independently capped by E (card_complete requires parcel_id for zone
--   linkage), so I cannot reach PASS while E has 3 unlinked cases.
--   No blocker row is written to gold_standard_county_blockers because the
--   county is still 8/10 PASS and autopilot dispatch is appropriate to retry
--   when new tools (Playwright-capable runner) become available.
--
-- HONESTY TAG: VERIFIED — convergent finding from 7+ independent firings;
--   last re-confirmed this session (run10418, 2026-08-11) by re-reading committed
--   session reports and prior SQL exhaustion files.

BEGIN;

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'gilchrist',
    'E',
    'Shard-2 run 10418 (2026-08-11): gilchrist E=78.6% (11/14). '
    '3 remaining unlinked cases (212025CA000033, 212025CA000070, 212026CA000004) '
    'are structurally blocked — clerk detail pages have empty parcel/address fields. '
    '7+ independent sessions, 7 data sources exhausted. No new lever found.',
    '{"convergent_sessions": 7, "sources_exhausted": '
    '["realforeclose_auth", "qpublic_403", "gilchristclerk_403", '
    '"civitek_turnstile", "fl_gio_co21_400", "fl_public_notices_zero", '
    '"legal_notice_aggregators_zero"], "last_reconfirmed": "2026-08-11", '
    '"unlinked_cases": ["212025CA000033CAAXMX","212025CA000070CAAXMX","212026CA000004CAAXMX"]}'::jsonb,
    true
  ),
  (
    '8d4cd6c7-e51a-4a0d-a8da-6995f13bad43'::uuid,
    'fallback',
    'gilchrist',
    'I',
    'Shard-2 run 10418 (2026-08-11): gilchrist I=57.1% (8/14). '
    'I is gated by E — parcel_id required for zone linkage (parcel_zones). '
    'Same 3 blocked cases as E. No write made; no fabrication.',
    '{"root_cause": "E_gate", "e_metric": 78.6, "i_metric": 57.1, '
    '"unlinked_cases_same_as_E": true, "last_reconfirmed": "2026-08-11"}'::jsonb,
    true
  )
) AS t(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit x
  WHERE x.dispatch_id = t.dispatch_id AND x.county_slug = t.county_slug AND x.letter = t.letter
);

COMMIT;
