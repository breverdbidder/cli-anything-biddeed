-- ARCHITECT TRIAGE issue #18303 (dispatch 30c5371a-d85d-4eea-a94f-f1db7870d925,
-- shard-2: pinellas/st_lucie/martin). Prior engineer attempt (GHA run 31118291331,
-- commit 051040ae) was externally cancelled ~20min in ("The operation was
-- canceled") and its post-run comment step also failed (exit 1) -- a silent end,
-- zero issue comments, but its committed scripts (stlucie_dispatch_group1/2)
-- WERE real, honest partial progress (st_lucie C/D/E moved 8->9/10 that session).
--
-- IDEMPOTENT RECORD of live REST writes already applied this session.
--
-- ── pinellas: E ghost-linkage purge (honesty fix, no DoD-letter flip) ──
-- 6 rows carried literal placeholder strings in parcel_id ('MULTIPLE PARCELS' x3,
-- 'Property Appraiser' x2, 'PERSONAL PROPERTY' x1) which satisfied pencil_dod's
-- naive `parcel_id IS NOT NULL` check for letter E, falsely inflating it (same bug
-- class as the citrus/miami_dade ghost-linkage purges, decision_log id=669).
-- E was already PASSING with margin (418/419=99.8%); purging drops it to
-- 412/419=98.3%, still comfortably >=95%. None of these 6 rows ever counted
-- toward I (card_complete) since the garbage strings never matched a real
-- v_zoning_gold_standard_card.parcel_id -- purging does not move I.
UPDATE multi_county_auctions SET parcel_id = NULL
WHERE county = 'pinellas' AND case_number IN (
  '522025CA003843XXCICI','522025CA006625XXCICI','522025CA000532XXCICI',
  '522019CA002273XXCICI','522024CC007590XXCOCO','522023CA006219XXCICI'
) AND parcel_id IN ('MULTIPLE PARCELS','Property Appraiser','PERSONAL PROPERTY');
-- NOTE (disclosed, not actioned -- out of surgical scope for this session):
-- 4 of these 6 rows also carry fabricated county-centroid lat=27.9/lon=-82.72
-- and assessed_value=150000 placeholders (the exact known-bad pattern documented
-- in 20260724_shard5_pinellas_i_real_parcel_geo_zone_fix.sql's own header comment
-- as "known-bad prior pattern... NOT repeated here"). Now parcel_id-null, they no
-- longer inflate I either way, but the placeholder lat/lon/value data itself is
-- still sitting in the table and should be nulled by a future session as a
-- separate, explicit data-hygiene pass.
--
-- ── st_lucie: letter I real zoning fix (7 rows, flips I FAIL->PASS) ──
-- BASELINE (live, this session): I=card_complete=112/125=89.6% FAIL (only fail;
-- A/B/C/D/E/F/G/H/J already PASS after the prior cancelled session's C/D/E work).
-- Root cause: 7 rows have a REAL parcel_id (E already counts them linked) but
-- fail I's stricter join into v_zoning_gold_standard_card (zone_code IS NOT
-- NULL) -- their zoning district was never spatially ingested. This is a NEW,
-- previously-undocumented residual, distinct from the historically-documented
-- 6 structurally-blocked E/I rows (AIRCRAFT/TIMESHARE/MULTIPLE PARCELS/Property
-- Appraiser label-leaks, re-confirmed unchanged this session, left untouched).
--
-- SOURCES (live ArcGIS REST queries this session):
--   - map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/MapServer/0
--     (St Lucie PA parcels -- AccountNumber/ParcelID/SiteAddress/geometry,
--     used to recover each parcel's real centroid and confirm address match
--     against the auction row on file)
--   - services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/Zoning/
--     FeatureServer/1 (PZ_ZONING, City of Port St. Lucie official zoning
--     districts -- jurisdiction_id=953) -- 5 of 7 parcels are incorporated PSL,
--     never previously queried against this source (prior sessions only queried
--     slcgis.stlucieco.gov, the COUNTY's unincorporated-only zoning layer)
--   - slcgis.stlucieco.gov/hosting/rest/services/LandUse/Zoning/MapServer/0
--     (unincorporated county layer, jurisdiction_id=1400) -- 2 of 7 parcels
-- Each match verified by spatial point-in-polygon at the PA parcel centroid,
-- AND by SiteAddress matching the auction row's on-file property_address.
--
-- 6 of 7 use zoning_districts rows that already existed (953/RS-2 id=11560,
-- 1400/PUD id=11562, 1400/HIRD id=11564) -- no G-denominator change.
-- 1 of 7 (114921, RM-8) required a NEW zoning_districts row (953/RM-8, no
-- prior FL RM-8 district existed for Port St Lucie). Verified live BEFORE
-- inserting that v_zoning_gold_standard_kpi_v3's density metric is computed
-- per PARCEL-ZONES ROW (246 applicable / 239 with real density value = 97.2%
-- baseline), not per unique zoning_districts code -- adding 1 more applicable-
-- but-value-missing row moves it to 247/239=96.8%, still >=95%, confirmed live
-- post-insert (actual result: G density=96.0%, PASS). RM-8's real max_density_
-- du_acre was NOT sourced this session: Port St Lucie Code of Ordinances
-- Sec. 158.078 lives on library.municode.com, which returned HTTP 403 to
-- WebFetch (JS-rendered SPA shell, 6KB, no content via curl either); the
-- design-standards.pdf mirror also 403'd; the portstlucie.elaws.us mirror
-- timed out (connects, never responds, this session). Per BLANK>WRONG this is
-- left NULL rather than guessed -- zone_code alone (not density) is what
-- letter I requires, so this does not block I, but a future session should
-- backfill the real RM-8 density value once municode is reachable.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
SELECT 953, 'RM-8', 'Multiple-Family Residential Zoning District (RM-8)', 'residential'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 953 AND code = 'RM-8');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('174976', 953, 'RS-2', 'Single-Family Residential', 'cityofpsl_arcgis_zoning_featureserver_20260806'),
  ('88586',  953, 'RS-2', 'Single-Family Residential', 'cityofpsl_arcgis_zoning_featureserver_20260806'),
  ('143032', 953, 'RS-2', 'Single-Family Residential', 'cityofpsl_arcgis_zoning_featureserver_20260806'),
  ('58966',  953, 'RS-2', 'Single-Family Residential', 'cityofpsl_arcgis_zoning_featureserver_20260806'),
  ('114921', 953, 'RM-8', 'Multiple-Family Residential', 'cityofpsl_arcgis_zoning_featureserver_20260806'),
  ('141313', 1400, 'PUD', 'Planned Unit Development', 'slcgis_zoning_mapserver_spatial_lookup_20260806'),
  ('3522-607-0028-000-7', 1400, 'HIRD', 'Unincorporated Residential (SLC Zoning Layer code)', 'slcgis_zoning_mapserver_spatial_lookup_20260806')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- VERIFIED live post-fix (pencil_dod_evaluate_county('st_lucie')):
--   st_lucie now 10/10 RAW: I=card_complete=119/125=95.2% PASS (was 89.6% FAIL),
--   G=density=96.0% PASS (was 97.2%, still well above 95%), all other 8 letters
--   unchanged/PASS.
--
-- ── certification gate: NOT closed this session (documented, not a bug) ──
-- gold_standard_certify() requires (a) survived=true gold_standard_ultraloop_audit
-- evidence for all 10 letters within a rolling 7 days, and (b) 2 CONSECUTIVE
-- gold_standard_loop() ticks where the county is fully gold (10/10 + fresh
-- audit + fresh precert guards). This session inserted 8 fresh survived=true
-- audit rows for st_lucie (A,B,C,D,F,G,H,J -- E and I already had fresh rows
-- from 2026-08-03), closing gap (a). Gap (b) was NOT closed: fleet-wide
-- gold_standard_certifications shows duval and marion (both outside this
-- shard, both currently certified=true) sitting at consecutive_non_gold=1 --
-- exactly one tick from the automatic revocation threshold
-- (consecutive_non_gold+1>=2). Calling the fleet-wide gold_standard_loop()+
-- gold_standard_certify() now, with multiple sibling shard sessions confirmed
-- mid-flight (several in_progress cc-runner-ghonly.yml GHA runs at triage
-- time), risks collaterally decertifying two counties this session does not
-- own, in direct tension with the PARALLEL-FLEET RULES shard-ownership
-- boundary and its explicit guidance ("Run the full loop + certify ONLY in
-- your close-out if no other session is mid-flight, otherwise skip loop and
-- report per-county evaluations"). Per that rule, loop()/certify() were
-- deliberately NOT run this session. st_lucie is now positioned to certify
-- on the next fleet tick where duval/marion's own status has independently
-- resolved (or a future session confirms zero collateral risk, per the
-- charlotte/pinellas precedent in decision_log ids 960/822).
--
-- martin: re-confirmed genuinely blocked, unchanged this session. 5/40 rows
-- have neither parcel_id nor a real street address at the source (2 are
-- future-dated 2026-09-29 auctions with no case detail published yet; 3 carry
-- only a generic "Stuart, Martin County, FL 34997" city/zip placeholder, no
-- street). No GIS lookup is possible without an address or parcel to anchor
-- on. C/D/E/I/J all fail as a direct cascade of these same 5 rows (auctions_
-- total=40, need 38/40 for every one of those letters). No autonomous fix
-- exists this session; not pursued further to stay within budget after the
-- st_lucie win.
