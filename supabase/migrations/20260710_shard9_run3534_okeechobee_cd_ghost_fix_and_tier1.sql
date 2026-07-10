-- GOLD STANDARD SHARD-9 — run3534 — okeechobee letters C/D
--
-- Part 1: ghost-success fix (same pattern as santa_rosa, shard1 alachua/gilchrist/putnam/manatee).
-- biddeed.refresh_parity_chunk (pg_cron job 45, fleet-wide) sets multi_county_auctions.
-- parity_status + parity_po_id from PropertyOnion matches but NEVER sets parity_source.
-- A prior shard-5 session (run651) left 6 okeechobee rows carrying a fake
-- 'tier1_clerk_supp_shard5_run651' parity_source label while parity_po_id was non-null on
-- ALL 6 (100%) -- proof they were PropertyOnion-derived matches wearing a false tier1_
-- label, not independent matches. PropertyOnion is a litmus/comparison source ONLY
-- (HARD GUARDRAILS #1) and must never count toward C/D.
--
-- Verified live before this migration was written:
--   SELECT case_number, parity_status, parity_source, parity_po_id
--   FROM multi_county_auctions
--   WHERE lower(county)='okeechobee' AND parity_source='tier1_clerk_supp_shard5_run651';
-- returned exactly the 6 case numbers below, all with non-null parity_po_id.

UPDATE public.multi_county_auctions
SET parity_source = 'po_derived_mislabeled_shard5run651',
    updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND parity_source = 'tier1_clerk_supp_shard5_run651'
  AND parity_po_id IS NOT NULL;
-- affected 6 rows: 472025CA000047CAAXMX, 472025CA000065CAAXMX, 472025CA000159CAAXMX,
-- 472025CA000214CAAXMX, 472025CC000297CCAXMX, 472025CC000342CCAXMX

-- Part 2: genuine tier1 coverage via realforeclose_aids (AJAX harvest, real data).
-- okeechobee.realforeclose.com / okeechobee.realtaxdeed.com are RealAuction-family
-- platforms; scripts/shard2_run2450_ajax_realforeclose_harvest.py (unmodified, existing,
-- already used for pinellas/santa_rosa/alachua/gilchrist/putnam/manatee) was run against
-- all okeechobee foreclosure auction dates (2026-03-11 .. 2026-09-17) and the single
-- tax_deed date on file (2026-04-09), harvesting 58 real AITEM records (case_number,
-- parcel_id, judgment_amount, property_address) into public.realforeclose_aids
-- (county_slug='okeechobee'). See scripts/shard9_run3534_okeechobee_harvest_targets.json
-- for the exact target list used.
--
-- This UPDATE joins multi_county_auctions against that genuinely-independent
-- realforeclose_aids data (NOT PropertyOnion) using the same guarded pattern as
-- refresh_shard2_cd_tier1_v1(): case_number normalized match (exact or containment) OR
-- parcel_id exact match GUARDED by a '~ [0-9]' digit-presence check on both sides to
-- reject scraper-failure sentinel strings ('Property Appraiser', 'MULTIPLE PARCELS',
-- 'MOBILE HOME', etc.) as per the false-positive class the santa_rosa v2 fix corrected.
-- (In this dataset every match landed via the case_number arm; the parcel_id arm's guard
-- is present defensively per the standing house pattern, not because it fired here.)

UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_aids_ajax_okeechobee',
    updated_at    = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'okeechobee'
  AND mca.county      = 'okeechobee'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      length(normalize_case_number(mca.case_number)) >= 10
      AND length(normalize_case_number(ra.case_number)) >= 8
      AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
    )
    OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
        AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]')
  )
  AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_aids_ajax_okeechobee';

-- Result (live, verified via pencil_dod_evaluate_county('okeechobee')):
--   before: C matched_clean=52/54 (96.3%, ghost-inflated) FAIL threshold display / D pass=true (ghost)
--   after ghost-fix only (part 1): C matched_clean=46/54 (85.2%) FAIL, D matched_any=46/54 (85.2%) FAIL
--   after tier1 harvest (part 2): C matched_clean=54/54 (100.0%) PASS, D matched_any=54/54 (100.0%) PASS
--
-- NOTE (observation, NOT fixed by this migration -- out of assigned scope, flagged for a
-- future session): two other okeechobee parity_source labels also show 100% co-occurrence
-- with non-null parity_po_id and warrant the same audit:
--   tier1_okeechobee_taxsmartweb_clerk_shard9:2026-07-02  (7 of 36 rows have parity_po_id
--     set -- NOT 100%, so most of that label's rows are NOT proven PO-derived; left
--     untouched, in scope only if a future session confirms the mechanism)
--   tier1_tax_deed_outcome (3 of 3 rows, 100% -- same shape as the confirmed ghost pattern,
--     but NOT in this task's explicit scope; do not act on this note without re-verifying
--     live first)
