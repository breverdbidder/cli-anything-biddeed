-- Gold Standard dispatch 8f944a71-a14f-4daa-bb6a-fe455c40c516 -- lee letters I + G
-- key=lee-I (property card completeness), lee-G (zoning coverage, caught as a
-- self-induced regression during this same fix -- documented per "any
-- regression = P0")
--
-- BASELINE (live, pencil_dod_evaluate_county('lee') at session start):
--   I: card_complete=316 of 341 = 92.7% (FAIL, threshold >=95% i.e. >=324, gap=8)
--   All other letters (A-H,J) PASS. auctions_total=341.
--
-- DIAGNOSIS: replicated the evaluator's exact card_complete predicate (address
-- + geo + assessed/market value + zoning-card linkage via parcel_zones/
-- v_zoning_gold_standard_card) live against paginated multi_county_auctions
-- (341 scoped rows) and v_zoning_gold_standard_card (318 zone_code-populated
-- rows for lee). 25 rows fail card_complete; of those, 10 fail ONLY on
-- zone_ok (address/geo/value already present) -- these 10 parcel_ids have NO
-- row in parcel_zones at all for lee, a genuine zoning-substrate coverage
-- gap, not a copy-forward/sync gap.
--
-- FIX (live research + PostgREST INSERT into public.parcel_zones, this
-- session): researched Lee County's real official zoning GIS sources and
-- resolved all 10 target parcels via authoritative point-in-polygon queries:
--   - Parcel geometry/STRAP crosswalk: LeePA (Lee County Property Appraiser)
--     https://gissvr.leepa.org/gissvr/rest/services/ParcelsWFS/MapServer/0
--     (FabricParcels layer, queried by Name=STRAP)
--   - Zoning polygons: Lee County GIS
--     https://gismapserver.leegov.com/gisserver910/rest/services/Layers/DCD_Zoning/MapServer
--     Layer 0 = unincorporated Lee County, Layer 1 = City of Cape Coral
--     (field LMLUZN), Layer 7 = City of Bonita Springs (field ZONING).
--     Note: maps.leegov.com / gis.leegov.com (the ArcGIS Hub/Portal front
--     end) do NOT serve raw REST JSON -- they redirect to a JS SPA -- the
--     working backend hostname (gismapserver.leegov.com/gisserver910) had to
--     be discovered via web search, not guessed.
--
--   10 rows inserted into public.parcel_zones (source='ArcGIS', new ids
--   872555-872564; pre-insert GET confirmed zero existing rows per
--   parcel_id, no duplicate risk):
--     20-44-24-C4-01260.0310  R-1B   (jurisdiction_id=815 Cape Coral)
--     22-44-26-L3-02028.0050  RS-1   (jurisdiction_id=630 Lee Unincorporated)
--     18-44-24-C4-00726.1070  R-3    (jurisdiction_id=815 Cape Coral)
--     21-45-27-L2-05022.0240  RS-1   (jurisdiction_id=630 Lee Unincorporated)
--     16-43-25-L2-0500H.0440  RPD    (jurisdiction_id=630 Lee Unincorporated)
--     27-44-26-L4-01007.0170  RS-1   (jurisdiction_id=630 Lee Unincorporated)
--     10-45-23-C3-00200.1030  R-3    (jurisdiction_id=815 Cape Coral)
--     18-44-23-06-00001.0680  RSC-1  (jurisdiction_id=630 Lee Unincorporated)
--     06-48-26-B3-0010C.0020  RPD    (jurisdiction_id=914 Bonita Springs)
--     25-43-23-C2-02335.0710  R-1B   (jurisdiction_id=815 Cape Coral)
--   effective_date/tax_account left NULL -- not provided by the source
--   endpoints, per BLANK > WRONG (not fabricated).
--
-- POST-FIX RESULT (immediate): I flipped to PASS, card_complete=324 of 341
-- (95.0%).
--
-- ============================================================================
-- SELF-CAUGHT REGRESSION (P0, same session -- "any regression = P0" per
-- CLAUDE.md CRITERION-PARALLEL PIVOT)
-- ============================================================================
-- The post-fix full pencil_dod_evaluate_county('lee') call (run immediately
-- after the I fix, standard verification protocol) showed G had flipped
-- PASS->FAIL: density=96.3 far=33.3 pk1000=80.0 (was density=97.6 far=100.0
-- pk1000=100.0 before this session's writes). Caught before commit/push --
-- not silently shipped.
--
-- ROOT CAUSE (live-diagnosed): of the 10 newly-linked zone_codes, 8 already
-- had a public.zoning_districts row (R-1B/RS-1x3/R-3x2/RPD, all correctly
-- flagged far_applicable=false, pk1000_applicable=false,
-- density_applicable=true by v_zoning_district_applicability, since these
-- are genuinely residential districts where FAR/parking-per-1000sf do not
-- apply -- FL convention, parking is per-dwelling-unit for residential).
-- The other 2 -- RSC-1 (jurisdiction_id=630) and RPD (jurisdiction_id=914) --
-- had NO zoning_districts row at all. v_zoning_gold_standard_kpi_v3's `pj`
-- CTE does `COALESCE(a.pk1000_applicable, true)` (and the equivalent for
-- far_applicable) whenever a parcel_zones.zone_code has no matching
-- zoning_districts row (LEFT JOIN miss) -- forcing these 2 residential
-- parcels to count as "applicable" for FAR and parking-per-1000sf with no
-- value, which they should never have been. This is the SAME documented
-- fleet-wide bug pattern already fixed once for Seminole (see
-- 20260718f_gold_standard_shard3_seminole_g_pk1000_applicability_fix_run26f01b9b.sql)
-- and previously worked around for Hendry/Hillsborough -- this session's fix
-- newly triggered it for Lee by being the first to link these 2 specific
-- zone_code/jurisdiction combos.
--
-- FIX: inserted the 2 missing public.zoning_districts rows with
-- category='residential' (matching the sibling RS-1@630 row's convention,
-- which the applicability view already resolves correctly to
-- far_applicable=false/pk1000_applicable=false/density_applicable=true when
-- a row exists) so the LEFT JOIN no longer misses:
--
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 630, 'RSC-1', 'Residential Single-Family/Conservation-1', 'residential',
       'Unincorporated Lee County residential single-family/conservation district (Matlacha area)'
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 630 AND code = 'RSC-1'
);

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 914, 'RPD', 'Residential Planned Development', 'residential',
       'City of Bonita Springs residential planned development (e.g. Hunters Ridge)'
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 914 AND code = 'RPD'
);
--
-- Both are genuinely residential districts (Matlacha-area single-family/
-- conservation, and Bonita Springs' Hunters Ridge RPD community) -- category
-- assignment reflects the real ordinance character, not a guess to force a
-- pass. Re-verified live via v_zoning_district_applicability immediately
-- after insert: both new district_ids (14224, 14225) resolve to
-- far_applicable=false, pk1000_applicable=false, density_applicable=true,
-- matching every other residential district in their jurisdictions.
--
-- ============================================================================
-- FINAL RESULT (this session, all letters, live re-verification)
-- ============================================================================
-- SELECT public.pencil_dod_evaluate_county('lee');
-- BEFORE (session start): I FAIL 92.7% (316/341); G PASS 97.6%; all else PASS.
-- AFTER (this session, final):
--   A PASS 43 | B PASS 100.0 | C PASS 100.0 | D PASS 100.0 | E PASS 96.8 |
--   F PASS 100.0 | G PASS 96.3 (density=96.3 far=100.0 pk1000=100.0) |
--   H PASS 0.0 | I PASS 95.0 (card_complete=324 of 341) |
--   J PASS 96.8 (deal_complete=330)
--   LEE IS 10/10 THIS SESSION. No other letter regressed (E/J unchanged at
--   96.8, matching pre-session values exactly; A/B/C/D/F/H unchanged).
--
-- This result was independently adversarially verified by a refuter
-- subagent (ULTRALOOP protocol) with live re-query access before being
-- reported -- see gold_standard_ultraloop_audit rows for county_slug='lee',
-- letter IN ('I','G'), dispatch_id='8f944a71-a14f-4daa-bb6a-fe455c40c516'.
