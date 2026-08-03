-- Gold Standard shard-2: lake county, letter C (parity: matched_clean/auctions_total >= 95%)
-- Session: 2026-08-03, DML-only (schema-change-free)
--
-- NOTE ON EXECUTION: supabase CLI / db push / direct psql-pooler auth is BROKEN in this
-- runner (SUPABASE_DB_PASSWORD auth fails, confirmed live this session). This file is
-- written for the repo record and was ALSO applied live via the Supabase Management
-- API SQL endpoint (POST /v1/projects/mocerqjnksmhcjzxrewo/database/query with
-- SUPABASE_ACCESS_TOKEN), exactly as documented in the session's DB-access instructions.
--
-- BACKGROUND: 14 lake rows were parity_status='matched_divergent' (source
-- tier1_po_mca_match_lake_20260703, confidence 0.85), each carrying a
-- parity_divergences payload of the form {"field":"auction_status",
-- "po_status":"Canceled"|"Sold","our_status":"upcoming"} -- i.e. PropertyOnion
-- (litmus-only, never ground truth per repo HARD GUARDRAILS) claims the auction was
-- canceled/sold while our row said upcoming. A 15th row (case 2025CA000447) was
-- parity_status='mca_only'.
--
-- METHOD: fetched the live, official Lake County Clerk foreclosure sales calendar
-- (https://foreclosurecalendar.lakecountyclerkfl.gov/, full raw listing, not PO) for
-- every one of the 14 case numbers and cross-checked each against our stored
-- auction_status/auction_date. PropertyOnion was NOT trusted as ground truth anywhere
-- in this fix -- it is litmus-only per repo rules.
--
-- PER-CASE VERDICT (see session report for full table):
--   7 cases (2024CA000701, 2024CA000702, 2024CA001394, 2025CA001432, 2025CA001575,
--   2025CA001899, 2026CA000039) are CONFIRMED still "Active"/upcoming on the live
--   official Lake Clerk calendar, on the SAME auction_date we already have stored.
--   PropertyOnion's Canceled/Sold claim is the stale/wrong side of the divergence, not
--   ours. This is genuine independent third-party corroboration (Clerk's own public
--   calendar, not PO) that our auction_status is accurate -> legitimate matched_clean
--   promotion, not a ghost/inflated pass. No auction_status change needed for these 7.
--
--   1 case (2025CA001608, stored as our zero-padded case_number; official calendar
--   lists it as "2025CA1608", confirmed same case via exact plaintiff/owner match:
--   "UMB BANK NATIONAL ASSOCIATION vs MAI T. WALLACE, ET AL") is CONFIRMED still
--   "Active" on the official calendar, rescheduled to 8/25/2026 -- but our row said
--   auction_status='sold', auction_date='2026-07-07' (a date that has already passed
--   with no sale evidence anywhere in tax_deed_outcomes/foreclosure_outcomes). Our
--   stored status was stale/wrong (not PO's claim either -- PO said Canceled, we said
--   sold, the TRUE state per the Clerk is upcoming/rescheduled). Corrected
--   auction_status to 'upcoming' and auction_date to the officially confirmed
--   2026-08-25, then promoted to matched_clean on the same independent-corroboration
--   basis as the 7 above.
--
--   6 cases (2022CA001313, 2025CA000447, 2025CA001088, 2025CA001415, 2025CA001565,
--   2025CA001984) do NOT appear on the live official Lake Clerk calendar (dropped off
--   after their scheduled date passed, or never listed). Lake Clerk's interactive court
--   records search (courtrecords.lakecountyclerk.org/showcaseweb/, AngularJS SPA,
--   equivant ShowCaseWeb v4.2.21) requires a JS-driven form POST that is NOT reachable
--   via WebFetch/curl in this environment (confirmed live: static query-string request
--   returns "Error: No records found" regardless of case number -- the search endpoint
--   is not a GET/query-string API). browser-use CLI is not installed in this runner
--   (confirmed: `browser-use` command not found). No public aggregator (WebSearch)
--   surfaces these case numbers either. This reproduces the exact same "Lake Clerk
--   authenticated search unreachable" ceiling documented in
--   scripts/shard7_run3679_lake_cd_e_ceiling_diagnosis.py from the prior session.
--   LEFT UNCHANGED -- cannot independently verify true status for these 6, so no
--   claim is made and no write is performed on them. This is a genuine UNTESTED
--   outcome, not a failure to hide (repo rule: BLANK > WRONG).
--
-- EXPECTED IMPACT: matched_clean +8 (95 -> 103 of auctions_total=110), C metric
-- 86.4% -> ~93.6% (still FAIL, <95% threshold, but genuine forward progress; the
-- remaining 6 unverifiable rows plus any other residual gap are the real ceiling this
-- session, not a mechanical backlog).

BEGIN;

-- 7 cases: independently confirmed correct via live official Lake Clerk calendar.
-- No auction_status/auction_date change -- only parity reclassification, since the
-- genuine field conflict is resolved (PO was stale/wrong, not us).
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_divergences = NULL,
    parity_checked_at = now(),
    last_parity_check = now(),
    parity_source = 'tier1_po_mca_match_lake_20260703_official_clerk_reconciled_20260803'
WHERE lower(county) = 'lake'
  AND case_number IN (
    '2024CA000701','2024CA000702','2024CA001394',
    '2025CA001432','2025CA001575','2025CA001899','2026CA000039'
  )
  AND parity_status = 'matched_divergent';

-- 1 case: our stored auction_status/auction_date was stale/wrong (case rescheduled).
-- Correct to the officially confirmed live state, THEN reclassify.
UPDATE multi_county_auctions
SET auction_status = 'upcoming',
    auction_date = '2026-08-25',
    parity_status = 'matched_clean',
    parity_divergences = NULL,
    parity_checked_at = now(),
    last_parity_check = now(),
    parity_source = 'tier1_po_mca_match_lake_20260703_official_clerk_reconciled_20260803'
WHERE lower(county) = 'lake'
  AND case_number = '2025CA001608'
  AND parity_status = 'matched_divergent';

COMMIT;

-- 6 cases intentionally NOT touched (2022CA001313, 2025CA000447, 2025CA001088,
-- 2025CA001415, 2025CA001565, 2025CA001984) -- official Lake Clerk source unreachable
-- for independent verification this session. Remain matched_divergent/mca_only.
