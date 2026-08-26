-- GOLD STANDARD shard-3 (dispatch 8d979d33-c6a4-4c6f-adfe-cd9f700cd117), seminole letter I
-- 2026-08-26 session. DOCUMENTATION-ONLY record of PostgREST PATCH statements
-- actually executed against production Supabase (mocerqjnksmhcjzxrewo) -- direct
-- psql/db push is unavailable in this environment (known constraint), so these
-- statements will NOT be re-applied by `supabase db push`. They are already
-- live; this file exists purely as an audit trail per repo convention.
--
-- CONTEXT: baseline (confirmed live via pencil_dod_evaluate_county('seminole')
-- at session start): I = card_complete=147 of 157 = 93.6% FAIL (need >=150/157).
-- auctions_total=157, all other letters (A-H, J) already PASS.
--
-- Two prior sessions today (commits d7798b55, and the 8182e55d shard-1 session
-- documented in GOLD_STANDARD_SHARD1_BREVARD_WALTON_HIGHLANDS_SEMINOLE_WASHINGTON_
-- DISPATCH_8182E55D_SESSION_REPORT.md) already closed this exact letter from
-- 90.4% -> 93.6% (5 of 6 zone-linkable rows fixed) and left a documented
-- "residual gap: 147/157 (need 150, gap=3)" note pointing at 3 specific
-- zone-link-only rows to re-diagnose fresh. This session re-diagnosed the full
-- 10-row gap from scratch against the live evaluator CTE (not from the note
-- alone) and found the gap composition unchanged in shape: 8 rows fail on
-- basic card fields (address/geo/value/parcel_id), 2 rows fail on zone-linkage
-- only. Of those 2 zone-only rows, one (SYN-SEM-2025CA000629) is the same
-- documented synthetic-parcel ceiling from the prior session. The other
-- (34-19-31-501-0000-2040 / 2657 Bullion Loop) was reconfirmed still
-- zone-unlinked and still outside all 3 known municipal ArcGIS zoning layers
-- (Sanford, Winter Springs, Lake Mary) -- same finding as the prior session,
-- re-verified live rather than assumed.
--
-- NEW THIS SESSION: adopted the FL DOH statewide parcels layer (see
-- scripts/property_appraiser/doh_statewide.py, commit a05a127d, seminole =
-- layer id 58 on https://maps.floridahealth.gov/server/rest/services/EHWATER/
-- Parcels/MapServer) as a fresh, independent, no-auth SSOT for assessed
-- value + polygon geometry (for centroid lat/lon) on 2 of the 8 basic-field
-- gap rows. This is a genuinely new avenue not used by either prior seminole-I
-- session (both of which relied on municipal ArcGIS zoning layers and the
-- dead scpafl.org/gis.scpafl.org endpoints for cards, not the DOH statewide
-- DOR NAL layer).
--
-- RESULT: both fixed rows got real, sourced value/geo, but did NOT flip
-- card_complete to true because both are also zone-link gaps (confirmed via a
-- fresh live point-in-polygon query against Sanford's "Zoning" ArcGIS Online
-- FeatureServer at each parcel's DOH-derived centroid: zero features, i.e.
-- outside the municipal zoning polygon despite a Sanford/Altamonte-Springs
-- postal address -- the same "postal address inside a city, land itself
-- unincorporated" pattern documented in the d7798b55 session for
-- 2657 Bullion Loop). I stayed at 147/157 (93.6%) -- no letter flip, but
-- real data-quality improvement with zero fabrication, and a corrected,
-- narrower diagnosis of the residual gap for the next session (see below).

-- === PATCH 1 ===
-- Row 58c361ca-4e50-4f71-b330-6235f11ef96c, case 20260071, tax_deed,
-- 203 BEDFORD RD, ALTAMONTE SPRINGS FL 32714, parcel_id 08-21-29-515-0C00-0020.
-- Source: FL DOH statewide parcels layer (Seminole, layer 58), PARCEL_ID
-- '0821295150C000020' (dash-stripped candidate format) -> AV_SD=136554,
-- JV=156689. Verified live 2026-08-26.
-- Executed via: PATCH $SUPABASE_URL/rest/v1/multi_county_auctions?id=eq.58c361ca-4e50-4f71-b330-6235f11ef96c
UPDATE multi_county_auctions
SET assessed_value = 136554,
    market_value = 156689,
    assessed_value_source = 'FL_DOH_statewide_parcels_seminole_layer58_PARCEL_ID_0821295150C000020'
WHERE id = '58c361ca-4e50-4f71-b330-6235f11ef96c';

-- === PATCH 2 ===
-- Row e096049f-45e3-46b9-9e97-ea0a25acaa3b, case 20260069/2024-000064,
-- N/A - MAGNOLIA AVE, SANFORD FL 32773, parcel_id 01-20-30-506-0000-2660.
-- Source: FL DOH statewide parcels layer (Seminole, layer 58), PARCEL_ID
-- '01203050600002660' -> AV_SD=81330, JV=81330, PHY_ADDR1='2656 S MAGNOLIA AVE'
-- (confirms the row's own address). Polygon geometry centroid computed from
-- the same DOH feature's rings (outSR=4326): lat=28.779814755925162,
-- lon=-81.26706480471866. Verified live 2026-08-26.
-- Executed via: PATCH $SUPABASE_URL/rest/v1/multi_county_auctions?id=eq.e096049f-45e3-46b9-9e97-ea0a25acaa3b
UPDATE multi_county_auctions
SET latitude = 28.779814755925162,
    longitude = -81.26706480471866,
    assessed_value = 81330,
    market_value = 81330,
    assessed_value_source = 'FL_DOH_statewide_parcels_seminole_layer58_PARCEL_ID_01203050600002660',
    geo_source = 'FL_DOH_statewide_parcels_seminole_layer58_polygon_centroid'
WHERE id = 'e096049f-45e3-46b9-9e97-ea0a25acaa3b';

-- === RESIDUAL GAP (10 rows, re-verify via pencil_dod_evaluate_county('seminole') at next session start) ===
--
-- ZONE-LINKAGE CEILING (3 rows) -- all confirmed live this session, each
-- queried against ALL known Seminole-area municipal ArcGIS zoning layers
-- (Sanford services1.arcgis.com/EPXb1p5YttfWtj8l/.../Zoning/FeatureServer/0,
-- Winter Springs services5.arcgis.com/hbtBppF7t3PpouVf/.../Planning_WFL1/
-- FeatureServer/5, Lake Mary services1.arcgis.com/v0YMSb0ovdJoIQKg/.../
-- LM_Zoning/FeatureServer/0) at each parcel's real coordinates, all
-- returning zero features (i.e. genuinely unincorporated county land despite
-- a city postal address -- a documented, common FL pattern):
--   34-19-31-501-0000-2040   2657 BULLION LOOP, SANFORD       (case 2025CA001957)
--   08-21-29-515-0C00-0020   203 BEDFORD RD, ALTAMONTE SPRINGS (case 20260071) -- value now fixed this session
--   01-20-30-506-0000-2660   2656 S MAGNOLIA AVE, SANFORD      (case 20260069/2024-000064) -- geo+value now fixed this session
-- Root blocker (re-verified live, still dead as of 2026-08-26, same as
-- documented in commit d7798b55): Seminole County's own unincorporated-area
-- zoning GIS server (seminolearcgis.seminolecountyfl.gov:6443, backing the
-- public "Zoning" webapp at seminolegis.maps.arcgis.com/apps/webappviewer/
-- index.html?id=0b9c7108874c40d6b54137133a07c86a) is unreachable --
-- connection timeout on all of :6443/https, :443/https, and :80/http, from
-- this environment. Also confirmed the county's ArcGIS Online hosted-services
-- org (services3.arcgis.com/n4VF6lyYfB5kizho, 124+ public services) carries
-- NO general unincorporated-county zoning layer among its hosted Feature
-- Services -- the real zoning data only exists behind the dead on-prem
-- server, proxied through the webapp viewer, not independently hosted.
-- Not a quick-fix gap; requires either that on-prem server coming back up,
-- or a different independent zoning source for unincorporated Seminole
-- County not yet found across 3 sessions of searching.
--
-- GENUINE VACANT-LOT / NO-SITUS-ADDRESS CEILING (1 row):
--   13-20-30-300-029A-0000  case 20260083/2024-001947, tax_deed. FL DOH
--   statewide layer confirms DOR_UC=099 (vacant, non-agricultural) and
--   PHY_ADDR1=' ' (blank in the county's own tax roll) -- there is no real
--   street address for this parcel in ANY source checked. Fabricating one
--   (e.g. from the STRAP or a generic "vacant lot" placeholder) would
--   violate the no-fabrication guardrail. AV_SD=15450 (value) and polygon
--   centroid (lat=28.744791750962, lon=-81.277510613239) ARE available and
--   real if a future session decides a null-address vacant-lot row should
--   still get partial backfill -- left untouched this session since it
--   would not change the pass/fail count without solving the address gap
--   AND (per the point-in-polygon check pattern above) still likely fails
--   zone-linkage for the same unincorporated-county reason.
--
-- SCRAPE-ARTIFACT CEILING (6 rows) -- each independently reconfirmed this
-- session via realforeclose_aids (a table populated by a DIFFERENT,
-- independent scrape-realauction-county.yml pipeline, not derived from
-- multi_county_auctions) and/or foreclosure_outcomes showing the exact same
-- garbage parcel_id, proving this is a genuine upstream data quality issue
-- on the source clerk calendar page, not a downstream join bug:
--   2025CA000060   parcel_id='MULTIPLE PARCELS'   (realforeclose_aids: 2 rows, both 'MULTIPLE PARCELS')
--   2024CA002388   parcel_id=NULL in mca, 'MULTIPLE PARCELS' in realforeclose_aids
--   2025CA002908   parcel_id=NULL in mca, 'LIQUORE LICENSE' in realforeclose_aids
--   2025CA002115   parcel_id='ALCOHOLIC LICENSE'  (no independent record found -- likely a real liquor-license/multi-parcel case with no single resolvable parcel)
--   2016CA000953   parcel_id=NULL in mca, 'Property Appraiser' in realforeclose_aids;
--                  address "58 BUTTONWOOD AVENUE, WINTER SPRINGS FL 32708" does
--                  NOT resolve to a single real parcel in the FL DOH statewide
--                  layer (nearest Buttonwood Ave/Dr/Ln/Ct/Way/Cir addresses in
--                  Winter Springs run even-numbered 200s-1180s; no "58" found)
--   SYN-SEM-2025CA000629   synthetic placeholder minted when the original
--                  scrape found no real parcel/address; foreclosure_outcomes
--                  independently shows the SAME 'Property Appraiser' artifact
--                  for this case_number (data_source
--                  'tier1_authoritative:seminole_fc_est_r1524')
-- These 6 are not zoning/geocoding problems -- the underlying court-calendar
-- scrape for these specific case numbers never captured a real parcel
-- identifier or address in the first place, on either our pipeline or the
-- independent realforeclose_aids pipeline. Genuine data ceiling per
-- guardrail #2 (no fabrication of parcel_id/address without a real source).
--
-- VERIFICATION (live pencil_dod_evaluate_county('seminole'), before and
-- after this session's 2 PATCH statements):
--   BEFORE: {"pass":false,"detail":"card_complete=147 of 157","metric":93.6}
--   AFTER:  {"pass":false,"detail":"card_complete=147 of 157","metric":93.6}
-- No letter flip (both fixed rows remain card_complete=false due to the
-- zone-linkage sub-condition), no regression, zero fabrication. All other
-- letters (A,B,C,D,E,F,G,H,J) confirmed unchanged/still PASS in the same
-- before/after query.
