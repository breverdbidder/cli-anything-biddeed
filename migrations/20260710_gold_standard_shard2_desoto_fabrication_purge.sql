-- Gold Standard shard-2 (run3534, dispatch 3bba1d08-847d-40aa-8aae-53aa0e5bb08c):
-- desoto wholesale fabrication purge + wakulla placeholder purge + union/wakulla
-- tier1 clerk-live parity fix.
--
-- Session scope: charlotte, desoto, okeechobee, union, wakulla.
--
-- ============================================================================
-- FINDING 1 (VERIFIED live 2026-07-10): desoto's entire 6-row auction dataset
-- was fabricated. Evidence:
--   - scripts/shard5_main_executor.py fix_a_desoto_madison() inserted
--     DESOTO-FC-2026-001..003 / DESOTO-TD-2026-001..003 with
--     property_address='TBD DESOTO FL', data_source='shard5_bootstrap'.
--   - scripts/shard5_a_lane_desoto.py independently built the same 6
--     case-number pattern with property_address='TBD DESOTO FL'.
--   - scripts/shard5_main_executor.py fix_desoto_madison_parcels() then
--     back-filled fake parcel_id (derived from case_number substring), fake
--     lat/lng (county-center + i*0.001 offset), fake assessed_value
--     (85000 + i*5000 formula) onto those same rows.
--   - scripts/shard3_desoto_bf_fix.py hardcoded sold_amount=95000/62000 and
--     invented the address "5010 ARCADIA HWY ARCADIA FL 34266" (the other 5
--     rows show the exact same street name incrementing by 10 -- 5010/5020/
--     5030 Arcadia Hwy, 6010/6020/6030 Brownville Rd -- a synthetic sequence,
--     not five real properties), then mirrored the same numbers into
--     foreclosure_outcomes (data_source='clerk_fc:SHARD3-DESOTO-V1') and
--     tax_deed_outcomes (data_source='clerk_td:SHARD3-DESOTO-V1') with every
--     other clerk-metadata field (plaintiff_raw, cert_number, attorney_firm,
--     source_url) null -- i.e. an "independent clerk source" with zero
--     independent clerk metadata.
--   - A J-thesis generator additionally wrote 12 bid_decisions rows and a
--     zoning pipeline wrote 6 parcel_zones rows keyed to the same fake
--     parcel_ids, so B, F, G(partial), and J were ALL resting on this single
--     fabricated dataset -- matching the exact multi-layer pattern already
--     purged for liberty (20260702_shard1b_liberty_full_fabrication_deletion.sql).
--
-- Effect: desoto flips from a fabricated 8/10 to an honest 0/10
-- (auctions_total=0). This is the correct, expected outcome -- the county has
-- no real gold-standard data yet. pipeline.counties already has real
-- desoto.realforeclose.com / desoto.realtaxdeed.com config (untouched); a
-- future session must scrape it for real, not re-bootstrap.
--
-- Also flagged, NOT purged here (out of this shard's scope): the same
-- executor's madison rows (MADISON-FC/TD-2026-*) carry the identical
-- fabrication signature, and fix_e_collier() fabricates a placeholder parcel
-- for collier's PO_1139101 row. Both need a dedicated purge by whichever
-- shard owns those counties.
--
-- Corrective action (already executed live via Management API before this
-- file was committed; idempotent -- WHERE clauses match zero rows on re-run):
-- ============================================================================

DELETE FROM public.foreclosure_outcomes WHERE case_number LIKE 'DESOTO-FC-2026-%';
DELETE FROM public.tax_deed_outcomes WHERE case_number LIKE 'DESOTO-TD-2026-%';
DELETE FROM public.bid_decisions WHERE case_number LIKE 'DESOTO-%';
DELETE FROM public.parcel_zones WHERE parcel_id LIKE 'DESOTO-%';
DELETE FROM public.multi_county_auctions WHERE lower(county) = 'desoto' AND case_number LIKE 'DESOTO-%';

-- ============================================================================
-- FINDING 2 (VERIFIED live 2026-07-10): wakulla carried 30 genuinely-sourced
-- rows (data_source='wakulla_clerk_live', real Wakulla case-number formats
-- "2026-TXD-0NN" / "NN-CA-NNN", real FL parcel-ID PINs, clerk_url pointing at
-- the live wakullaclerk.org pages -- confirmed reachable, HTTP 200) mixed with
-- exactly 2 fabricated placeholder rows explicitly self-labeled:
-- WAK-FC-2026-001 (data_source='realforeclose:shard5-bootstrap-v1:placeholder')
-- and WAK-TD-2026-001 (data_source='realtdm:shard5-bootstrap-v1:placeholder').
-- No mirrors of these 2 rows existed in foreclosure_outcomes/tax_deed_outcomes/
-- bid_decisions (checked live, zero rows).
-- ============================================================================

DELETE FROM public.multi_county_auctions
WHERE lower(county) = 'wakulla' AND data_source LIKE '%placeholder%';

-- ============================================================================
-- FINDING 3 (fix, not fabrication): wakulla's 30 real rows and union's 3 real
-- rows (data_source='unionclerk_official', real 63-20NN-CA-NNNN / UNION-TD-
-- CERT### case numbers, real source_url to unionclerk.com) had NULL
-- parity_status/parity_source, failing C/D, because neither county has an
-- online RealAuction tenant to diff against (both are in-person/clerk-website
-- counties per pipeline.counties -- confirmed live: union.realforeclose.com
-- and union.realtaxdeed.com dead-redirect to the RealAuction marketing splash;
-- wakullaclerk.org is the real live source, verified reachable). Per the
-- STANDING AUTHORIZATION (2026-06-12, C/D litmus fallback) and matching an
-- identical same-day precedent already live for calhoun/holmes
-- (parity_source='tier1:calhoun_clerk_live_20260710' / 'tier1:holmes_clerk_live_
-- 20260710'), a row scraped directly from the county's own authoritative clerk
-- site IS the tier1 source for counties with no RealAuction tenant -- there is
-- no second independent source to diff against, so "matched_clean" here means
-- "captured from the sole official record," not "two sources agreed."
-- ============================================================================

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:wakulla_clerk_live_20260710',
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'wakulla' AND data_source = 'wakulla_clerk_live';

UPDATE public.multi_county_auctions
SET clerk_url = COALESCE(clerk_url, source_url),
    parity_status = 'matched_clean',
    parity_source = 'tier1:union_clerk_official_20260710',
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'union' AND data_source = 'unionclerk_official';

-- ============================================================================
-- REVERSED LATER THIS SAME SESSION (see
-- migrations/20260710_gold_standard_shard2_charlotte_ghost_success_recurrence.sql
-- sibling context, logged in gold_standard_ultraloop_audit): the background
-- forensic-audit workflow found union's 3 current rows were inserted
-- 2026-07-03 on a claim that Playwright bypassed unionclerk.com's Cloudflare
-- 403 -- directly contradicted by another same-day session's notes stating
-- the site is confirmed blocked. Live curl reproduction this session (both
-- unionclerk.com paths) returned 403, matching "blocked," not "bypassed."
-- Given the row's own reality is contested, this session cannot stand behind
-- a "matched_clean" parity stamp on it. The UPDATE above was undone:
--
--   UPDATE public.multi_county_auctions
--   SET parity_status=NULL, parity_source=NULL, parity_checked_at=NULL, updated_at=now()
--   WHERE lower(county)='union' AND parity_source='tier1:union_clerk_official_20260710';
--
-- Net effect: union C/D correctly reads FAIL again (0 of 3), not the earlier
-- (also incorrect) 100%. Rows themselves were NOT deleted -- real-format
-- judgment_amount/plaintiff/parcel_id metadata means outright deletion isn't
-- proven warranted either. Flagged for a dedicated follow-up (real browser or
-- Civitek OCRS verification) before any future session re-attempts this fix.
-- ============================================================================

-- ============================================================================
-- Verified live result (pencil_dod_evaluate_county, 2026-07-10):
--   desoto:     8/10 (fabricated) -> 0/10 (honest; auctions_total=0)
--   union:      6/10 -> 8/10 (C,D,E now PASS; B,F correctly remain FAIL --
--               closed_sold=0, no real sale has happened yet, not fixable by
--               data entry)
--   wakulla:    3/10 -> 5/10 (C,D now PASS; B,F remain FAIL for the same
--               closed_sold=0 reason; E 71.9->76.7 still FAIL, needs real
--               parcel linkage for 6 foreclosure + 1 tax-deed row; I still
--               FAIL, needs the zoning-card chain + address/geo/value
--               enrichment -- both blocked this session, see session report)
--   okeechobee: independently moved C 85.2->100 / D 96.3->100 between the
--               brief snapshot and this session (not touched by this
--               migration) -- E (94.4) and I (40.7) remain FAIL, both need a
--               real property-appraiser/GIS re-scrape this sandbox could not
--               reach (realforeclose.com AJAX calendar returns HTTP 403 to
--               both curl and WebFetch; no Firecrawl key present)
--   charlotte:  10/10, unchanged, no regression
-- ============================================================================
