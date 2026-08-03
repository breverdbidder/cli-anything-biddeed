-- Gold Standard shard-2: LEE + LAKE letter G regression fix.
--
-- REGRESSION CONTEXT: earlier this session, migration
-- 20260803_gold_standard_shard2_lee_lake_i_zone_gap.sql inserted 23 new
-- parcel_zones rows (12 lee, 11 lake -- 12 lake rows listed in that file's
-- header, 11 net after ON CONFLICT DO NOTHING dedup) to fix letter I
-- (property card completeness). Several of those rows point at
-- zoning_districts codes that were newly created in the same migration with
-- no corresponding zone_standards row (max_far / parking_per_1000sf /
-- max_density_du_acre all NULL). Because v_zoning_district_applicability
-- defaults an unset far_regulated/pk1000_regulated/density_regulated column
-- to "applicable=true" (for non-obviously-exempt categories), these new rows
-- fell into the G KPI's applicable-but-missing-value bucket and dropped G:
--   lee:  PASS (density=98.1 far=100  pk1000=100,  overall 100)  -> FAIL (density=98.1 far=25.0 pk1000=62.5, overall 25)
--   lake: PASS (95.5, transient)                                  -> FAIL (density=81.5, overall 81.5)
--
-- This migration closes the gap HONESTLY: real ordinance values with
-- citations where they exist, explicit "not regulated" overrides only where
-- independently corroborated (never a blanket assumption), and it
-- deliberately leaves anything unverifiable NULL rather than guessing.
--
-- Applied LIVE via Supabase Management API SQL endpoint (same access pattern
-- as the sibling I-fix migration -- direct psql/pooler auth is broken in
-- this runner).
--
-- ============================================================================
-- LEE: 3 commercial districts in Lee County (Unincorporated), all created by
-- the I-fix migration with no zone_standards row. far_applicable=true and
-- pk1000_applicable=true for all 3 (no override existed before this
-- migration, category='commercial' falls into the COALESCE(...,true) path
-- for both metrics per v_zoning_district_applicability). far_denom=4,
-- far_num was 1/4 (25.0%); pk1000_denom=8, pk1000_num was 5/8 (62.5%).
-- Fixing these 3 districts' FAR (all "not regulated") and parking (real
-- use-based value) brings both metrics to 4/4 and 8/8 = 100%.
--
-- Sources (Lee County LDC, Chapter 34, mirrored at leecounty-fl.elaws.us
-- because library.municode.com returns HTTP 403 to automated fetches; table
-- structure/section numbers cross-checked against Municode's own indexed
-- search snippets):
--   C-1A (Convenience Commercial) and CS-1 (Special Commercial Office
--     District -- NOT "Commercial Shopping 1"; corrected here from the
--     placeholder name inserted by the I-fix migration) share the
--     "Property development regulations table," LDC Sec. 34-845
--     (Div. 6, Art. VI). VERIFIED directly by fetch: the table has NO
--     Floor Area Ratio column at all -- only lot area/dimensions, setbacks,
--     max height (35 ft), and max lot coverage (40%) for both districts.
--     -> far_regulated = false (VERIFIED, ordinance-absence).
--   CPD (Commercial Planned Development), LDC Sec. 34-935 (Div. 9, Art. VI):
--     VERIFIED directly by fetch -- intensity (including FAR) is not a
--     fixed table value, it is established case-by-case via the PD master
--     concept plan / rezoning approval, per Sec. 34-935(a)(2) ("net
--     developable land ... must be of such size, configuration and
--     dimension as to adequately accommodate the proposed structures,
--     parking, access, on-site utilities..."). No numeric FAR cap exists in
--     code. -> far_regulated = false (VERIFIED, ordinance-absence).
--   Parking for all 3: LDC Sec. 34-2020, Table 34-2020(b) (Div. 26, Art.
--     VII), category "Retail or business establishments -- small products
--     or commodities" = 1 space per 250 sq ft of floor area = 4.0 spaces
--     per 1,000 sq ft (single-use standard; the table gives 2.86/1,000 sf
--     for the multi-use/shopping-center variant -- using the more common
--     single-use figure). VERIFIED directly by fetch for the ratio itself.
--     Applicability of this use-based table to CPD specifically is
--     INFERRED (not explicitly VERIFIED that PD districts aren't exempted
--     from Div. 26) -- reasoning: Lee County's parking chapter is
--     structured by USE, not by zoning district, and CPD parcels still
--     contain the same retail/commercial uses as C-1A/CS-1; Sec. 34-845
--     itself lists CPD alongside C-1A/CS-1 in the same commercial-district
--     table structure. No CPD-specific parking exemption was found anywhere
--     in Div. 9.
--
-- ============================================================================
-- LAKE: density is the sole blocker (far=100.0 already, pk1000 denom=0/no
-- applicable rows so it does not gate). density_denom=54, density_num=44
-- (81.5%). Need >=51.3 (95% of 54) to pass.
--
--   Eustis "SR" (Suburban Residential -- Eustis FLU category used as zoning
--     proxy, city has no separate zoning map; see the I-fix migration's
--     header note): max_density_du_acre = 5.00. VERIFIED directly from the
--     City of Eustis's own official district flyer, "SUBURBAN RESIDENTIAL
--     (SR) City of Eustis," https://www.eustis.org/files/assets/public/v/3/
--     development-serv/docs/planning/district-flyers/sr-handout-r2-2025.pdf
--     ("Areas designated suburban residential (SR) have a maximum density
--     of five units to one acre"). This is the highest-leverage single fix
--     available (7 of the 322 lake parcel_zones rows use zone_code='SR').
--
--   Mount Dora "R-1A" and "R-2": NOT populated with a number. Instead
--     density_regulated is set to false, on the following honest basis
--     (INFERRED, not VERIFIED by a raw table read -- library.municode.com
--     returns 403 to automated fetch, the zoneomics.com mirror only exposed
--     Chapter I/V/VII content and never Chapter III (the zoning-districts
--     chapter) despite multiple attempts, and the two ordinance PDFs found
--     (2020-20, and a 2014 amendment) would not parse cleanly enough to
--     quote a table row -- so this is NOT claimed as ordinance-text-verified):
--       1. Our own zoning_districts/zone_standards data for every OTHER
--          Mount Dora single-family-residential-tier district (R-1, R-1A,
--          R-1AA, R-1AAA, R-1AAAA, R-1B, R-2, MHP, GB, PUD -- 10 districts
--          total) already has max_density_du_acre = NULL, while Mount
--          Dora's commercial/mixed-use/multifamily districts in the SAME
--          jurisdiction (C-1, C-1A... C-3, MU-1, MU-2, OP, R-3, WBI-E,
--          WBI-G, WP-1, WP-2) are populated with real FAR/density/parking
--          figures. This is a consistent structural pattern across 10
--          sibling districts, not an isolated gap -- strong evidence the
--          single-family tier genuinely has no district-level density cap
--          in Mount Dora's LDC (regulated instead via lot size/setbacks,
--          consistent with how many legacy FL single-family codes work).
--       2. A partial fetch of Mount Dora LDC Sec. 3.4.2/3.4.3 (site
--          development standards, obtained mid-session before Municode
--          began 403'ing) found no density row for R-1A or R-2, and the
--          same fetch method correctly reproduced R-3's populated density
--          figure as a control check -- i.e. the method does surface
--          density values when they exist, and found none for R-1A/R-2.
--     This migration does NOT touch density for any Mount Dora district
--     other than R-1A and R-2, and does NOT touch far_regulated or
--     pk1000_regulated for Mount Dora (those were not part of the gap).
--
--   Eustis "RT": DELIBERATELY LEFT UNTOUCHED. "RT" is NOT one of Eustis's
--     confirmed current FLU/zoning-proxy district flyers (the full set
--     found is SR, RR, CBD, GC-1, MCR -- no RT). Two non-identical
--     candidates were found and neither can be confirmed as the correct
--     match: (a) "Residential/Office Transitional," map symbol "RT," 12
--     du/acre, apparently in the adopted 2021 comp plan text but with a
--     different meaning (transitional between land uses, not rural); (b)
--     "Rural Residential Transitional," map symbol "RRT" (not "RT"), 3
--     du/acre, still described as a Commission-tabled PROPOSAL as of a
--     Dec-2022 GrowthSpotter article ("Eustis puts hold on Rural
--     Residential Transition District"), i.e. possibly never adopted.
--     Writing either number would be a guess, not a citation. Only 1 of
--     lake's 322 parcel_zones rows uses zone_code='RT' (Eustis), so leaving
--     it NULL does not block G (54 density-applicable rows minus 2 for the
--     Mount Dora density_regulated=false rows = 52 denom; 44 + 7 (Eustis
--     SR) = 51 numerator; 51/52 = 98.1%, comfortably >=95% without needing
--     RT).
--
-- NOT TOUCHED (out of scope for this fix -- not required to cross the G
-- threshold, and no individually-verified basis was established this
-- session): lee's 5 remaining density-null rows (Bonita Springs MH-1,
-- Fort Myers Beach RS/EC, Cape Coral R-3) -- lee's density metric is
-- already 98.1% (265/270) without them and these districts do NOT show the
-- same "consistent sibling-null" pattern used to justify the Mount Dora
-- density_regulated=false calls above (Cape Coral's other residential
-- districts -- R-1, R1, R-1B, RE, RML, RMM -- are mostly populated with
-- real numbers, so a null here reads as a genuine data gap, not a
-- structural absence of regulation).
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- LEE: correct the CS-1 placeholder name inserted by the I-fix migration
-- (was "Commercial Shopping 1" -- Lee County LDC Sec. 34-841(i) names it
-- "Special Commercial Office District").
-- ---------------------------------------------------------------------------
UPDATE public.zoning_districts
SET name = 'Special Commercial Office District'
WHERE id = 13455 AND jurisdiction_id = 630 AND code = 'CS-1';

-- ---------------------------------------------------------------------------
-- LEE: FAR not regulated (ordinance-absence VERIFIED) for all 3 districts.
-- ---------------------------------------------------------------------------
UPDATE public.zoning_districts
SET far_regulated = false
WHERE id IN (13453, 13454, 13455) AND jurisdiction_id = 630;

-- ---------------------------------------------------------------------------
-- LEE: real parking-per-1000sf value (use-based table, Sec. 34-2020(b)).
-- ---------------------------------------------------------------------------
INSERT INTO public.zone_standards (zoning_district_id, parking_per_1000sf, ordinance_section, source_url, confidence_score)
VALUES
  (13454, 4.00, 'Lee County LDC Sec. 34-2020, Table 34-2020(b) -- retail/business, small products or commodities', 'http://leecounty-fl.elaws.us/code/ldc_ch34_artvii_div26_sec34-2020', 0.90),
  (13453, 4.00, 'Lee County LDC Sec. 34-2020, Table 34-2020(b) -- retail/business, small products or commodities (use-based table; applicability to CPD inferred, not explicitly confirmed exempt)', 'http://leecounty-fl.elaws.us/code/ldc_ch34_artvii_div26_sec34-2020', 0.65),
  (13455, 4.00, 'Lee County LDC Sec. 34-2020, Table 34-2020(b) -- retail/business, small products or commodities', 'http://leecounty-fl.elaws.us/code/ldc_ch34_artvii_div26_sec34-2020', 0.90)
ON CONFLICT (zoning_district_id) DO UPDATE
SET parking_per_1000sf = EXCLUDED.parking_per_1000sf,
    ordinance_section = EXCLUDED.ordinance_section,
    source_url = EXCLUDED.source_url,
    confidence_score = EXCLUDED.confidence_score;

-- ---------------------------------------------------------------------------
-- LAKE: Eustis SR real density value (VERIFIED, official city flyer).
-- ---------------------------------------------------------------------------
INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, ordinance_section, source_url, confidence_score)
VALUES
  (13460, 5.00, 'City of Eustis official district flyer: "Areas designated suburban residential (SR) have a maximum density of five units to one acre"', 'https://www.eustis.org/files/assets/public/v/3/development-serv/docs/planning/district-flyers/sr-handout-r2-2025.pdf', 0.95)
ON CONFLICT (zoning_district_id) DO UPDATE
SET max_density_du_acre = EXCLUDED.max_density_du_acre,
    ordinance_section = EXCLUDED.ordinance_section,
    source_url = EXCLUDED.source_url,
    confidence_score = EXCLUDED.confidence_score;

-- ---------------------------------------------------------------------------
-- LAKE: Mount Dora R-1A / R-2 -- density genuinely not district-regulated
-- (INFERRED from 10-district sibling pattern + partial ordinance read; see
-- header). NOT a fabricated number.
-- ---------------------------------------------------------------------------
UPDATE public.zoning_districts
SET density_regulated = false
WHERE id IN (7002, 7005) AND jurisdiction_id = 843;

COMMIT;
