-- Gold Standard dispatch 8f944a71-a14f-4daa-bb6a-fe455c40c516 -- brevard letter I
-- key=brevard-I (county=brevard, letter=I, property card completeness)
--
-- BASELINE (pencil_dod_evaluate_county('brevard') before fix, this session):
--   I: card_complete=6267/7300 = 85.8% (FAIL, threshold >=95% i.e. >=6935)
--   All other letters (A-H,J) PASS. Gap to close: 668 rows.
--
-- PRIOR-SESSION CONTEXT (dispatch a96722e9, scripts/gold_standard_shard1_
-- a96722e9_brevard_i_bcpao_nal_backfill.py, already committed to this repo):
-- ran the identical county-GIS-keyed backfill approach against an earlier
-- snapshot (7252 total, 981 addr-missing) and found ZERO writable address
-- rows -- 929/981 genuinely STREET_NAME=UNKNOWN in Brevard County's own
-- live authoritative GIS parcel layer, 51 with no GIS feature at all. This
-- session independently RE-RAN that same proven script fresh against the
-- current row set (drifted to 7300 total via new auction rows) to get
-- today's own before/after evidence rather than trusting the stale finding.
--
-- RE-DIAGNOSIS (this session, live re-run of scripts/gold_standard_shard1_
-- a96722e9_brevard_i_bcpao_nal_backfill.py against gis.brevardfl.gov's
-- Base_Map/Parcel_New_WKID2881/MapServer/5, TaxAcct-keyed, 848 distinct
-- parcel_ids queried across the addr+geo+value buckets):
--
--   ADDRESS bucket (977 rows missing property_address, 976 numeric TaxAcct):
--     applied: 0
--     STREET_NAME=UNKNOWN/blank at the county's own GIS (genuine no-situs
--       parcel, confirmed live): 926
--     no GIS feature at all for TaxAcct (parcel not in county's own live
--       parcel fabric -- confirmed via both the 150-per-batch IN-list query
--       AND a standalone single-TaxAcct equality re-query on a sample of 4
--       [2000772, 2001369, 2539270, 2218184] -> `"features":[]` from the
--       live service each time, ruling out a batching/WAF artifact): 50
--     non-numeric (STRAP-style) parcel_id, not TaxAcct-queryable: 1
--
--   GEO bucket (60 rows missing BOTH latitude AND po_latitude, numeric
--   TaxAcct present): of these, 4 resolved against a real GIS feature with
--   usable polygon geometry and were APPLIED (see UPDATE statements below);
--   56 had no GIS feature at all (same no-feature parcels as the address
--   bucket's structural block).
--
--   VALUE bucket (4 rows missing both assessed_value AND market_value):
--     applied: 0 -- all 4 have no GIS feature (same no-feature parcels).
--
-- CROSS-CHECK against a second internal table (this session, NOT in the
-- prior a96722e9 script): queried public.sample_properties (BCPAO NAL-
-- sourced, keyed by tax_account) for all 836 unique parcel_ids in the
-- address-gap bucket. 782/836 matched a sample_properties row; of those,
-- 777 (99.4%) also have address='UNKNOWN' or blank in sample_properties,
-- and 758/782 (97%) are building_value=0 (vacant land). This independently
-- corroborates the county GIS finding via a second BCPAO-derived source:
-- the address gap is dominated by genuinely addressless vacant-land parcels
-- (small-dollar tax-deed/tax-certificate lots), not a sync/copy-forward gap
-- -- no internal table in this database (parcel_zones, zoning_assignments,
-- sample_properties) carries a real, non-fabricated address for this
-- population. parcel_zones itself was also checked and has no address
-- column at all (zone_code/zone_name/jurisdiction_id only), ruling out the
-- pasco-style "known-real value exists elsewhere, just not copied" pattern
-- for this specific letter/county.
--
-- bcpao.us direct fetch: re-confirmed live this session via WebFetch against
-- https://www.bcpao.us/PropertySearch/#/parcel/2003885 -> HTTP 403 (Cloudflare
-- managed challenge), consistent with the prior session's curl-based finding.
-- Not re-attempted via Firecrawl for the 50 no-feature parcels this session
-- (out-of-budget for a bucket capped at 50 rows against a 668-row gap; see
-- RESIDUAL section below).
--
-- FIX APPLIED (live, this session, via PostgREST PATCH -- idempotent, each
-- guarded by "latitude IS NULL AND longitude IS NULL AND parcel_id=eq.<id>"
-- at write time): 4 rows in the GEO bucket had a real GIS feature with
-- computable polygon centroid and were backfilled with live-sourced lat/lon
-- from gis.brevardfl.gov (WGS84 / outSR=4326, centroid of feature geometry
-- ring). These UPDATE statements reproduce the already-applied PATCH:
--
UPDATE public.multi_county_auctions
SET latitude = 27.9650840575109,
    longitude = -80.6248760559875,
    updated_at = NOW()
WHERE lower(county) = 'brevard' AND case_number = '260072'
  AND parcel_id = '2934299'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 27.93465207915,
    longitude = -80.6417401651967,
    updated_at = NOW()
WHERE lower(county) = 'brevard' AND case_number = '260074'
  AND parcel_id = '2944584'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 27.9185038366482,
    longitude = -80.6671775797453,
    updated_at = NOW()
WHERE lower(county) = 'brevard' AND case_number = '260077'
  AND parcel_id = '2947893'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 27.8817518337783,
    longitude = -80.527217076635,
    updated_at = NOW()
WHERE lower(county) = 'brevard' AND case_number = '260093'
  AND parcel_id = '3002959'
  AND latitude IS NULL AND longitude IS NULL;

-- ============================================================================
-- RESULT (this session)
-- ============================================================================
-- rows_fixed: 4 (geo bucket only)
-- rows_still_blocked: ~1033 across addr(977)+geo(56)+value(4) buckets minus
--   overlap (a single row can be missing more than one field; distinct
--   row count still short of card_complete is 7300-6271=1029)
--   - 926 addr rows: STREET_NAME=UNKNOWN at Brevard's own authoritative GIS
--     (genuine no-situs vacant/small-lot parcels) -- STRUCTURAL BLOCK,
--     independently corroborated by sample_properties (777/782 also
--     address=UNKNOWN). Not forced. BLANK > WRONG.
--   - 55 rows (addr+geo+value overlap): zero GIS feature in Brevard's own
--     live parcel fabric for that TaxAcct at all -- confirmed via both
--     IN-list batch query and standalone single-TaxAcct spot-check on 4
--     samples. Likely retired/merged/pre-fabric certificate numbers.
--     STRUCTURAL BLOCK, not forced.
--   - 1 row: non-numeric (STRAP-format) parcel_id, not TaxAcct-queryable
--     against this GIS layer. Not attempted this session (would need a
--     different join key; out of proportion to a 1-row yield).
--   - 41 rows with NULL parcel_id (drifted from 32 at last diagnose to 41
--     this session -- confirms this is a live-shifting population of newly
--     scheduled auctions, not a stable backlog): 29 scheduled, 6 cancelled,
--     3 completed, 3 upcoming. No case-to-parcel identity established yet;
--     would require per-case clerk.brevardclerk.us docket lookup. Not
--     attempted this session -- disproportionate one-by-one research cost
--     for a bucket this size relative to the 668-row gap, and several rows
--     are cancelled/out of the evaluator's likely scope. Flagged as
--     NEEDS_LIVE_HARVEST residual for a future session, not silently
--     dropped.
--
-- metric_moved: YES (small, real, non-fabricated). card_complete
--   6267 -> 6271 (85.8% -> 85.9%). Letter I remains FAIL (needs >=6935).
--   This is the honest ceiling reachable via legitimate enrichment this
--   session -- the dominant remaining gap (926+55=981 rows, ~98% of the
--   990-row shortfall to threshold) is a confirmed structural block: the
--   county's own system of record has no situs address/geometry for these
--   parcels, corroborated by a second independent BCPAO-derived table
--   (sample_properties). Forcing a value here would violate the HARD
--   GUARDRAIL against fabricating address/geo data.
--
-- RESIDUAL / NEXT-SESSION LEVERS (not attempted this session, ascending
-- cost order, per HONESTY PROTOCOL -- do not silently drop):
--   a. Firecrawl bcpao.us per-account scrape for the 55 zero-GIS-feature
--      TaxAccts only (NOT the 926 confirmed-UNKNOWN ones -- re-scraping
--      those would spend against an already-negative, twice-corroborated
--      signal). Ceiling if 100% successful: +55 rows max (85.9% -> 86.7%),
--      still short of 95%.
--   b. clerk.brevardclerk.us docket lookup for the 29 scheduled + 3
--      completed NULL-parcel_id rows to establish parcel identity, then
--      chain into GIS/BCPAO lookup. Ceiling: +32 rows max, same order of
--      magnitude as (a), does not close the 668-row gap alone.
--   c. Even combining (a)+(b) in the best case (+87 rows), letter I would
--      reach ~87.1%, still well short of 95%. The 926-row UNKNOWN-street
--      population is the true structural ceiling on this letter for this
--      county and is not solvable via enrichment -- it would require
--      Brevard County itself assigning situs addresses to parcels that
--      currently have none in its own system of record. This matches the
--      canon-level finding (GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_
--      FINDING) pattern of a genuine, verified real-world ceiling rather
--      than an unexploited lever.
--
-- ============================================================================
-- VERIFICATION (run after applying)
-- ============================================================================
-- SELECT public.pencil_dod_evaluate_county('brevard');
-- BEFORE: {"I":{"pass":false,"detail":"card_complete=6267 of 7300","metric":85.8}}
-- AFTER:  {"I":{"pass":false,"detail":"card_complete=6271 of 7300","metric":85.9}}
-- All other letters (A,B,C,D,E,F,G,H,J) unchanged and PASS both before and
-- after -- no regression, no drift from concurrent fleet sessions observed.
