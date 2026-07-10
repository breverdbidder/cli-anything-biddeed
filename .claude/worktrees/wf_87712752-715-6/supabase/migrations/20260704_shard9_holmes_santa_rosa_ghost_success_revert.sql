-- SHARD-9 (osceola/holmes/walton/santa_rosa/sumter): holmes + santa_rosa ghost-success revert
-- dispatch_id: 1745c67a-1636-4250-939e-d79532ccb20b
-- Session: architect-20260704T000000
--
-- Found via an ultracode Workflow fan-out (4 diagnose agents + 4 adversarial refuters, one per
-- county) plus independent main-session re-verification of every claim before acting.
--
-- HOLMES (C/D reported 75.0%, real number much lower):
-- Of the 12 "matched_clean" rows counted by pencil_dod_evaluate_county (parity_source LIKE
-- 'tier1%%'), only 1 is genuinely backed:
--   - HOLMES-LEGACY-123a1bd5-... : parity_source='tier1_foreclosure_outcome', backed by a real
--     foreclosure_outcomes row with data_source='holmes_clerk_direct' and a real, resolvable
--     source_url (https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/). KEPT.
-- The other 11 are fabricated:
--   - 3 rows (HOLMES-FC-PAST-001/002, HOLMES-TD-PAST-001): synthetic paired MCA+outcome rows.
--     Sequential placeholder addresses (100 Maple Rd / 200 Cedar St / 300 Pine Ave, same
--     city/zip), sequential fake parcel_ids (HOLMES-FO-0008/-0009, HOLMES-TA-0010), literal
--     "PAST" in the case number (not a real FL clerk convention), all 3 MCA rows share one
--     identical microsecond created_at (2026-06-25T08:11:00.248551Z), the matching
--     tax_deed_outcomes row for HOLMES-TD-PAST-001 is DUPLICATED with two conflicting
--     auction_dates (2026-05-01 vs 2026-05-15), and all outcome-table source_url fields are
--     NULL despite one data_source claiming to be "official". These fabricated pairs are why
--     the canonical matcher (refresh_parity_tier1_outcomes) legitimately labeled them
--     'tier1_foreclosure_outcome'/'tier1_tax_deed_outcome' -- the join succeeded only because
--     both sides of the join were fabricated together.
--   - 8 rows (TD#2020-349, TD#2023-185, TD#2023-225, TD#2023-330, TD#2023-509, TD#2023-584,
--     TD#2023-753, TD#2024-185): parity_source='tier1_clerk_holmes_shard8_20260702', a label
--     the canonical matcher is STRUCTURALLY INCAPABLE of producing (its source only ever
--     writes 'tier1_tax_deed_outcome'/'tier1_foreclosure_outcome', and only for auction_status
--     IN ('redeemed','completed','sold','cancelled','canceled') -- every one of these 8 rows
--     is auction_status='upcoming'). Confirmed zero backing: none of these 8 case_numbers or
--     their parcel_ids exist anywhere in tax_deed_outcomes/foreclosure_outcomes (both tables
--     combined have exactly 2 and 3 rows respectively for holmes, none matching).
--   - 3 more rows (HOLMES-LEGACY-14b20609, TD#2020-589, TD#2023-496) carry
--     parity_source='clerk_official_court_format' with equally zero backing in either outcome
--     table. This label does not start with 'tier1' so it was already excluded from the
--     evaluator's matched_clean/matched_any count -- nulling it here is a data-hygiene
--     correction, not a scoreboard change.
-- ACTION: delete the 3 fully-synthetic MCA rows + their 2 foreclosure_outcomes + 2
-- tax_deed_outcomes counterparts; null parity_status/parity_source on the 11 remaining
-- unbacked-label rows (8 shard8-labeled + 3 clerk_official_court_format-labeled). The 1
-- genuinely-backed LEGACY row is untouched.
--
-- SANTA_ROSA (C/D reported 92.1%, this session's own RPC call already partially corrected it,
-- this migration finishes the job):
-- ALL 58 of santa_rosa's original "matched_clean" rows carried parity_source
-- ='tier1_realforeclose_santa_rosa' -- a label the canonical matcher cannot produce, and
-- IMPOSSIBLE to be a genuine outcome match: tax_deed_outcomes and foreclosure_outcomes both
-- have ZERO rows for santa_rosa county-wide (confirmed live), so no case_number could ever
-- legitimately join to a real sale outcome. Worse, the 30 rows this label still applies to
-- (post the workflow's one `refresh_parity_tier1_outcomes` call, which wiped the 28 rows whose
-- auction_status made them wipe-eligible) are ALL auction_status='upcoming' -- a claim of
-- "verified matched_clean" against an auction that has not even happened yet, which is
-- definitionally impossible. This is NOT a regression caused by this session's RPC call (an
-- earlier read of the diff mischaracterized it that way) -- the RPC's wipe was honest and
-- correct; the label was fabricated before this session touched anything, and the 28
-- wipe-eligible rows plus these remaining 30 upcoming rows are the same single fabrication,
-- just split across two auction-status buckets by the RPC's wipe scope.
-- ACTION: null parity_status/parity_source on the remaining 30 rows carrying
-- 'tier1_realforeclose_santa_rosa'. Post-migration, santa_rosa's honest C/D = 0/63 (0.0%) --
-- there is genuinely zero verified-outcome data for this county yet, which is the true state.

BEGIN;

-- ── HOLMES ──
DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'holmes'
   AND case_number IN ('HOLMES-FC-PAST-001','HOLMES-FC-PAST-002');

DELETE FROM tax_deed_outcomes
 WHERE lower(county) = 'holmes'
   AND case_number = 'HOLMES-TD-PAST-001';

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'holmes'
   AND case_number IN ('HOLMES-FC-PAST-001','HOLMES-FC-PAST-002','HOLMES-TD-PAST-001');

UPDATE multi_county_auctions
   SET parity_status = NULL, parity_source = NULL, updated_at = now()
 WHERE lower(county) = 'holmes'
   AND case_number IN (
     'TD#2020-349','TD#2023-185','TD#2023-225','TD#2023-330',
     'TD#2023-509','TD#2023-584','TD#2023-753','TD#2024-185',
     'HOLMES-LEGACY-14b20609-70d3-434b-b7a3-e8c45c3ca882',
     'TD#2020-589','TD#2023-496'
   );

-- ── SANTA ROSA ──
UPDATE multi_county_auctions
   SET parity_status = NULL, parity_source = NULL, updated_at = now()
 WHERE lower(county) = 'santa_rosa'
   AND parity_source = 'tier1_realforeclose_santa_rosa';

-- ── ULTRALOOP audit trail ──
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'holmes', 'C',
   'holmes matched_clean=12 of 16 (75.0%)',
   '{"verdict":"CONFIRMED_FABRICATED","real_matched_clean":1,"real_pct":6.25,"fabricated_case_numbers":["HOLMES-FC-PAST-001","HOLMES-FC-PAST-002","HOLMES-TD-PAST-001","TD#2020-349","TD#2023-185","TD#2023-225","TD#2023-330","TD#2023-509","TD#2023-584","TD#2023-753","TD#2024-185"],"genuine_row_kept":"HOLMES-LEGACY-123a1bd5-1ea3-4bb4-98ad-a7fc86853e49 (backed by holmes_clerk_direct, real source_url)","evidence":"8 rows carry a parity_source the canonical matcher structurally cannot produce (only touches non-upcoming auction_status, these are all upcoming); 3 rows are synthetic paired MCA+outcome fixtures with sequential placeholder data"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'holmes', 'D',
   'holmes matched_any=12 of 16 (75.0%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"same root cause as C"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'holmes', 'B',
   'holmes verified=3 of closed_sold=3 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"all 3 backing rows are the synthetic HOLMES-FC/TD-PAST fixtures deleted by this migration"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'holmes', 'F',
   'holmes tier1_sold=3 of closed_sold=3 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"same fabricated rows as B"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'santa_rosa', 'C',
   'santa_rosa matched_clean=58 of 63 (92.1%), later 30 of 63 (47.6%) after a same-session canonical-matcher call',
   '{"verdict":"CONFIRMED_FABRICATED","real_matched_clean":0,"real_pct":0.0,"evidence":"the sole parity_source value in use (tier1_realforeclose_santa_rosa) is not producible by the canonical matcher and applies exclusively to auction_status=upcoming rows (auctions that have not occurred); foreclosure_outcomes and tax_deed_outcomes both have ZERO rows for santa_rosa county-wide, so no case_number could ever legitimately be a verified match. Not a regression from the RPC call made this session -- the RPC exposed, rather than caused, the fabrication."}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'santa_rosa', 'D',
   'santa_rosa matched_any=58 of 63 (92.1%), later 30 of 63 (47.6%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"same root cause as C"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'walton', 'C',
   'walton matched_clean=13 of 30 (43.3%), improved to 15 of 30 (50.0%) via the canonical matcher this session',
   '{"verdict":"REAL_IMPROVEMENT_CONFIRMED","evidence":"refresh_parity_tier1_outcomes reclassified 2 genuinely matched_divergent rows (2026-0001TD, 25CA000453) to matched_clean via real case-number join against tax_deed_outcomes/foreclosure_outcomes; independently re-verified live, all case numbers/addresses/parcel_ids check out as genuine FL clerk data, not fabricated"}'::jsonb,
   true),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'sumter', 'E',
   'sumter parcel_linked=7 of 11 (63.6%)',
   '{"verdict":"CONFIRMED_GENUINE_GAP","evidence":"4 unlinked rows are real foreclosure-PDF-sourced auctions lacking parcel_id because the source PDF only lists case_number+address, not folio number; Sumter County Property Appraiser (qpublic.schneidercorp.com) address-search returned HTTP 403 (anti-bot) when attempted this session -- genuinely blocked, not fabricatable"}'::jsonb,
   true);

COMMIT;
