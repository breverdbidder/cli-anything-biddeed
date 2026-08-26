-- GOLD STANDARD shard-4 (dispatch b9413c05-7731-40be-ad53-0c7c9b3fd878), counties
-- bradford/madison, 08:00Z wave, 2026-08-26. Documents live PostgREST data
-- writes applied directly during this session (direct psql unavailable per
-- the standing pooler SNI constraint -- PostgREST/service-role REST used
-- instead, consistent with the established pattern for this pipeline). No
-- schema changes; this file is an audit-trail record of INSERT-only data
-- operations already applied live.
--
-- MADISON: I FAIL->PASS (75.0%->100.0%, 6/8->8/8 card_complete). Root cause:
-- 2 tax-deed parcels (21-2N-09-5288-022-000 case 26-7-TD,
-- 21-2N-09-5288-021-000 case 26-9-TD) already had complete address/geo/value
-- but no zone_code linkage -- prior sessions (dispatch 97478bee, 2026-08-25)
-- got as far as confirming a live UMN MapServer 6.4.3 backend at
-- gz.floridapa.com/mapserver but could not find the correct "map" CGI
-- parameter after 5 naming-pattern guesses.
--
-- THIS SESSION'S UNBLOCK: used a real headless-Chromium (Playwright) page
-- load of https://planning.madisoncountyfla.com/gis/ and captured the
-- browser's own outgoing WMS GetMap network requests, which revealed the
-- vendor's actual naming convention: /www/_grizzly.gis/gis.MadisonPA.com/
-- ol_<LayerName>.map. Brute-forcing that confirmed prefix against a short
-- list of plausible layer names found ol_Parcel.map (singular) live and
-- WMS-capable (GetCapabilities lists layers parcel/parcel1-3/parcelquery/
-- parcelqoutline/parcelqfill/parcelhl etc). WFS DescribeFeatureType is
-- disabled on this mapfile, but WMS GetFeatureInfo against the "parcelquery"
-- layer at each parcel's existing stored lat/lon (SRS=EPSG:4326, one of the
-- mapfile's advertised CRSes) returns a PIN + "PARCELTAG2" text attribute
-- straight from the Madison County Property Appraiser's own live parcel
-- database:
--   PIN=212N095288022000 PARCELTAG2='21-2N-09-5288-022-000 (VACANT)~ISBELL ANN B~N SR 53~FLU/ZON: Agriculture 2 (A2) | 0.67AC'
--   PIN=212N095288021000 PARCELTAG2='21-2N-09-5288-021-000 (VACANT)~ISBELL JAMES S~N SR 53~FLU/ZON: Agriculture 2 (A2) | 0.6AC'
-- Both PINs match the target parcel_ids exactly (dashes stripped). This is
-- the county PA's own authoritative GIS attribute, not PropertyOnion, not an
-- inferred guess.
--
-- "Agriculture 2 (A2)" is a real, distinct Madison County LDC Chapter 4
-- zoning district (separate from the existing "A-1 Agriculture 1" district
-- already in this table for jurisdiction_id=1188) -- confirmed by fetching
-- the same ordinance PDF already on file for A-1
-- (https://madiscon-county-fl.s3.amazonaws.com/uploads/2025/05/28151409/
-- Chapter-4-Land-Use-Districts-and-Development-Standards.pdf) and locating
-- "SCHEDULE 1.0 MINIMUM DEVELOPMENT STANDARDS": the table row for
-- "Agriculture 2" reads: Max Building Height 35 ft, Density 1 du/10 ac,
-- FAR 0.5, Lot coverage 35%, Front/Corner/Side/Rear setbacks 40/40/20/40 ft.
-- These are real ordinance-sourced numbers (not fabricated/inferred-by-
-- analogy), so far_regulated/density_regulated are set true (mirroring A-1),
-- with a real zone_standards row. Parking is not specified for agricultural
-- districts in this schedule, so parking_per_unit/parking_per_1000sf are
-- left NULL (madison's G metric shows pk1000 blank/not-applicable for this
-- county already, so this does not create a fabricated-standard risk).
--
-- Post-write live re-verify: pencil_dod_evaluate_county('madison') shows
-- I: PASS card_complete=8 of 8 (100.0), G: unchanged PASS density=100.0
-- far=100.0 (no regression from adding the new district). Full county now
-- 7/10 (up from 6/10). B ("verified=0 closed_sold=0"), C (matched_clean=7 of
-- 8, sole genuine CLERK_SSOT_CANCELLED row 25-128-CA), and F
-- ("tier1_sold=0 closed_sold=0") remain FAIL -- all three reconfirmed as
-- genuine structural ceilings with FRESH live evidence this session (11th+
-- consecutive session reaching this conclusion for B/F; see session report
-- for the full re-check trail: madisonclerk.com foreclosure-sales page still
-- lists only future case 25-79-CA with no post-sale results archive;
-- auctions_total unchanged at 8; case 25-128-CA still genuinely
-- status='cancelled' at the clerk source).
--
-- BRADFORD: B/F reconfirmed FAIL (closed_sold=0) as a genuine structural
-- ceiling for the 14th+ consecutive session, with fresh live evidence today
-- against the two cases that newly crossed past-due thresholds since the
-- last check (25000439CAAXMX/25000487CAAXMX, auction_date 2026-08-13, now
-- 13 days past; 24000431CAAXMX, auction_date 2026-08-20, now 6 days past):
-- bctelegraph.com's 8-20-26 weekly edition contains zero mentions of any of
-- these case numbers (only an unrelated case's pre-sale notice); Bradford
-- has no RealAuction/RealForeclose mirror (in-person courthouse sale,
-- confirmed in prior sessions), so the RealForeclose "Auction Results
-- Report" lever that fixed Bay county's B/F this week does not apply;
-- myfloridacounty.com/orisearch/04 and bradfordclerk.com remain
-- Cloudflare-Turnstile-gated (reconfirmed live, no bypass attempted per
-- campaign guardrails against CAPTCHA/detection-evasion tooling). No writes
-- applied to bradford this session. BLANK > WRONG.
--
-- All claims above (madison-I fix, bradford B/F ceiling, madison B/F
-- ceiling, madison C ceiling) were independently adversarially verified via
-- a 4-agent ULTRALOOP Workflow fan-out this session and logged as individual
-- rows in gold_standard_ultraloop_audit (dispatch_id=
-- b9413c05-7731-40be-ad53-0c7c9b3fd878). gold_standard_campaign checkpoint
-- updated with per-county criteria_passed for the next session to resume
-- from.
--
-- This file is documentation-only (the INSERT statements below were already
-- applied live via PostgREST during the session; re-running them here is a
-- no-op by design, using the same ON CONFLICT / WHERE NOT EXISTS idempotency
-- pattern this repo's other gold-standard migrations use).

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, description, ordinance_section)
SELECT 1188, 'A-2', 'Agriculture 2', 'agricultural', true, true, NULL,
  'Predominantly agricultural/silvicultural use lands, distinct from Agriculture 1 (higher allowed density: 1 du/10ac vs 1 du/40ac).',
  'Section 4.4.B / Schedule 1.0'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 1188 AND code = 'A-2');

INSERT INTO public.zone_standards (zoning_district_id, max_height_ft, max_density_du_acre, max_far, max_lot_coverage_pct, front_setback_ft, corner_setback_ft, side_setback_ft, rear_setback_ft, source_url, ordinance_section, confidence_score)
SELECT zd.id, 35, 0.1, 0.5, 35.0, 40.0, 40.0, 20.0, 40.0,
  'https://madiscon-county-fl.s3.amazonaws.com/uploads/2025/05/28151409/Chapter-4-Land-Use-Districts-and-Development-Standards.pdf',
  'Section 4.4.B / Schedule 1.0', 0.9
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1188 AND zd.code = 'A-2'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, effective_date, source)
SELECT '21-2N-09-5288-022-000', 1188, 'A-2', 'Agriculture 2', 'Agriculture 2 (A2)', '2026-08-26',
  'madison_county_pa_gis_gz_floridapa_ol_Parcel_map_PARCELTAG2:PIN212N095288022000'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '21-2N-09-5288-022-000');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, effective_date, source)
SELECT '21-2N-09-5288-021-000', 1188, 'A-2', 'Agriculture 2', 'Agriculture 2 (A2)', '2026-08-26',
  'madison_county_pa_gis_gz_floridapa_ol_Parcel_map_PARCELTAG2:PIN212N095288021000'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '21-2N-09-5288-021-000');
