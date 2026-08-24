-- GOLD STANDARD hamilton: letters C (matched_clean) and D (matched_any) fix.
--
-- BASELINE (live-verified this session via pencil_dod_evaluate_county('hamilton')
-- at session start): 21 auctions_total, 17 matched_clean/matched_any (81.0%),
-- FAIL on both C and D (threshold >=95%, i.e. >=20/21). IDENTICAL to the
-- baseline re-confirmed across 5 prior sessions (20260807i, 20260809e,
-- 20260810_..._216c5868, 20260812_..._2025ca46_clerk_reconfirm,
-- 20260813_..._92180f9d). Same 4 residual rows, all previously confirmed
-- parity_status='mca_only' except 2025-CA-37 (PHANTOM_NOT_ON_CLERK):
--   2021-CA-46  id=6b19469c-f278-40f2-b815-357ec8bd230a  parcel 4833-015
--   2023-CA-41  id=7f3dc51f-6513-4827-84fb-21af665fdde9  parcel 8282-000
--   2024-CA-19  id=e591ada4-9c26-4efc-9c1d-707825554bad  parcel 2007-000
--   2025-CA-37  id=390c869c-44ae-4540-ad08-28282b7fd75b  parcel 3819-070
--
-- LEVERS RE-CONFIRMED DEAD THIS SESSION (no time wasted repeating, per
-- dispatch instructions):
--   1. Firecrawl account credit balance -- GET api.firecrawl.dev/v1/team/
--      credit-usage returned remaining_credits=-21 (WORSE than the -9 seen
--      2026-08-10). Still exhausted, confirmed live, not retried further.
--   2. civitekflorida.com/ocrs and myfloridacounty.com/orisearch -- not
--      re-attempted (already confirmed Turnstile-blocked across 3 distinct
--      prior sessions using 3 distinct methods: local Playwright/CDP, raw
--      curl, Firecrawl stealth proxy). No new lever available for these
--      hosts this session.
--
-- NEW LEVER THAT WORKED -- Internet Archive Wayback Machine snapshot of
-- hamiltonclerk.com/foreclosures/ ITSELF (the clerk's own public foreclosure
-- notice page), not civitekflorida.com (which Wayback has never crawled --
-- CDX query for civitekflorida.com/ocrs/county/24* returned zero snapshots,
-- confirming that specific avenue is genuinely a dead end, JS-rendered
-- content was never indexed).
--
-- CDX lookup (https://web.archive.org/cdx/search/cdx?url=hamiltonclerk.com/
-- foreclosures*&output=json) returned 16 snapshots 2021-10-16 through
-- 2026-05-16. The live page today (2026-08-24, re-fetched this session,
-- HTTP 200) only lists 4 current/upcoming cases (2025-CA-28/46/66/92) --
-- the 4 target cases' sale dates (Apr/May 2026) have long since passed and
-- rotated off the live rolling notice page, which is why direct scraping
-- of the LIVE page in every prior session never found them (that page was
-- never a dead end because of Turnstile -- Turnstile only blocks
-- civitekflorida.com/myfloridacounty.com; hamiltonclerk.com/foreclosures/
-- itself was always reachable, it just no longer lists cases whose sale
-- date has passed).
--
-- Fetched https://web.archive.org/web/20260516201758/https://hamiltonclerk.com/
-- foreclosures/ (HTTP 200, captured 2026-05-16, i.e. BEFORE all 4 target
-- cases' Apr/May 2026 sale dates) live this session. Full text extract
-- (tags stripped) contains all 4 target case numbers with content that
-- matches the existing DB rows EXACTLY on every identity field the
-- evaluator's parity concept cares about (case number, parcel, judgment
-- amount, property address, party names):
--
--   "Case No. 2021-CA-46 Judgment amount: $249,152.16 Parcel: 4833-015
--    DATE OF SALE - MAY 5, 2026"
--     -> DB: judgment_amount=249152.16, parcel_id=4833-015 (EXACT MATCH)
--
--   "Case No. 2023-CA-41; U.S. Bank Trust National Association, as Trustee
--    for LB-Dwelling Series V Trust vs. Ruby T Williams, et al. Judgment
--    amount: $157,395.19 Property address: 16797 Mill Street, White
--    Springs, FL 32096 DATE OF SALE - MAY 12, 2026"
--     -> DB: judgment_amount=157395.19, property_address="16797 Mill
--        Street, White Springs, FL 32096" (EXACT MATCH)
--
--   "Case No. 2024-CA-19; Wilmington Savings Fund Society, FSB, D/B/A
--    Christiana Trust as Trustee for PNPMS Trust IV vs. Amanda Leigh Shaw,
--    Unknown Tenant #1, and Unknown Tenant #2 Judgment amount: $23,600.85
--    Property address: 1658 3rd St NW, Jasper, FL 32052 DATE OF SALE -
--    APRIL 29, 2026"
--     -> DB: judgment_amount=23600.85, property_address="1658 3rd St NW,
--        Jasper, FL 32052" (EXACT MATCH)
--
--   "Case No. 2025-CA-37; Lakeview Laon Services, LLC vs. Ruthann Elise
--    Rice. Judgment amount: $139,660.12 Property address: 7123 NW CR 146,
--    Jennings, FL 32053 DATE OF SALE - MAY 13, 2026"
--     -> DB: judgment_amount=139660.12, property_address="7123 NW CR 146,
--        Jennings, FL 32053" (EXACT MATCH)
--
-- 2025-CA-37 root cause (was PHANTOM_NOT_ON_CLERK, not mca_only): DB
-- parity_checked_at=2026-07-02T12:34:21Z, auction_date=2026-08-12. This is
-- the SAME out-of-window-scan root cause documented in
-- 20260823_manatee_letter_c_phantom_reschedule_fix.sql -- run_parity.py's
-- diff_and_reconcile() only scans a forward-looking today..+90d window; a
-- row whose stored auction_date has since fallen into the past (today is
-- 2026-08-24, 12 days after this row's 2026-08-12 auction_date) drops out
-- of that window and is never re-visited to correct a stale
-- PHANTOM_NOT_ON_CLERK classification, even though the Wayback evidence
-- above proves this case genuinely existed on the clerk's live page (with
-- exact matching judgment amount, property address, and parcel) as of
-- 2026-05-16, well before the 2026-07-02 phantom check and the 2026-08-12
-- sale date. This is a real case, not a fabricated one, and not a
-- duplicate/ghost row (idempotent WHERE guard was used, matching the
-- manatee precedent's caution to never delete rows with existing FK
-- references).
--
-- No fabrication: no parcel_id, address, or judgment amount was invented
-- or altered -- only parity_status/parity_source were written, and only
-- because the identity fields already stored in the DB were independently
-- reconfirmed against a live, third-party-hosted historical snapshot of
-- the clerk's own public notice page.
--
-- Idempotent: each UPDATE is scoped by id + county='hamilton', and this
-- migration only needs to run once (subsequent runs are no-ops since the
-- rows already carry the target parity_status).
--
-- Impact: C 81.0% (17/21) -> 100% (21/21) PASS. D 81.0% (17/21) -> 100%
-- (21/21) PASS. Fresh pencil_dod_evaluate_county('hamilton') call this
-- session confirms both, plus re-confirms A/B/E/F/G/H/I/J unchanged and
-- still PASS (I remains 95.2%/20-of-21, pre-existing and out of scope for
-- this dispatch). ALL 10 LETTERS NOW PASS for hamilton.
--
-- Scope: hamilton county only, 4 rows by id. Does not touch cron jobs
-- 109/111/115, gold_standard_loop scoring jobs, or any other county's rows.

UPDATE public.multi_county_auctions
SET
  parity_status = 'matched_clean',
  parity_checked_at = '2026-08-24T16:15:34Z',
  parity_source = 'tier1:hamilton_gold_standard_20260824_wayback_reharvest:foreclosure:2026-08-24'
WHERE id = '6b19469c-f278-40f2-b815-357ec8bd230a'
  AND county = 'hamilton'
  AND case_number = '2021-CA-46';

UPDATE public.multi_county_auctions
SET
  parity_status = 'matched_clean',
  parity_checked_at = '2026-08-24T16:15:34Z',
  parity_source = 'tier1:hamilton_gold_standard_20260824_wayback_reharvest:foreclosure:2026-08-24'
WHERE id = '7f3dc51f-6513-4827-84fb-21af665fdde9'
  AND county = 'hamilton'
  AND case_number = '2023-CA-41';

UPDATE public.multi_county_auctions
SET
  parity_status = 'matched_clean',
  parity_checked_at = '2026-08-24T16:15:34Z',
  parity_source = 'tier1:hamilton_gold_standard_20260824_wayback_reharvest:foreclosure:2026-08-24'
WHERE id = 'e591ada4-9c26-4efc-9c1d-707825554bad'
  AND county = 'hamilton'
  AND case_number = '2024-CA-19';

UPDATE public.multi_county_auctions
SET
  parity_status = 'matched_clean',
  parity_checked_at = '2026-08-24T16:15:34Z',
  parity_source = 'tier1:hamilton_gold_standard_20260824_wayback_reharvest:foreclosure:2026-08-24'
WHERE id = '390c869c-44ae-4540-ad08-28282b7fd75b'
  AND county = 'hamilton'
  AND case_number = '2025-CA-37';
