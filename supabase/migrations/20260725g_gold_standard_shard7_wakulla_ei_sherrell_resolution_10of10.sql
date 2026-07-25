-- Gold Standard shard-7 wakulla, dispatch 55e44a55-29b3-45cf-8edd-46bf8d547803, run6459
-- (2nd firing of this exact dispatch -- 1st firing, commit c8adb060, was an honest no-op:
-- E/I both FAIL at 93.3%, blocked on 2 residual rows -- case 25-CA-68 (Sherrell, ambiguous
-- between 2 candidate parcels) and 2026-TXD-097 (redeemed, no deed ever issued -- permanent
-- gap). Both prior sessions independently confirmed qpublic.schneidercorp.com 403-blocked
-- (Cloudflare) and Firecrawl at 0 credits, with no channel left to disambiguate Sherrell's
-- 2 owned parcels.
--
-- THIS SESSION found a genuinely new, non-CAPTCHA-gated channel: FL DOR's public bulk tax
-- roll data portal (floridarevenue.com/property/dataportal -- no login, no Cloudflare) hosts
-- Wakulla's Name-Address-Legal (NAL) assessment roll as a plain downloadable zip, searchable
-- offline by owner name. This surfaced the same 2 Sherrell-owned parcels prior sessions found
-- (093S01E00005159000, the Section-9 homestead at 885 Woodville Hwy; and 293S01E24405506A02,
-- a Rio Paz Subdivision vacant lot) but for the first time supplied their legal-description
-- fields for disambiguation.
--
-- Disambiguation: the actual published Notice of Foreclosure Sale for Case 2025-CA-68
-- (Cadles of West Virginia LLC vs Carolyn Sherrell, The Wakulla Sun, 2026-07-02/07-09,
-- retrieved live via floridapublicnotices.com) describes "PARCEL 1" by metes-and-bounds
-- beginning on the easterly ROW of US Hwy 319 in "Section 9, Township 3 South, Range 1
-- East" -- an exact match to the homestead parcel's DOR SEC/TWN/RNG fields (9/03S/01E) and
-- S_LEGAL ("9-3S-1E P-76-M-75B"). The Rio Paz parcel's legal description ("RIO PAZ
-- SUBDIVISION", no SEC/TWN/RNG set, no homestead exemption) matches neither Parcel 1 nor the
-- notice's separate river-tract "PARCEL 2" description -- it was a false candidate.
--
-- Parcel ID crosswalk confirmed live: DOR NAL format "093S01E00005159000" corresponds to
-- Wakulla Property Appraiser / pipeline format "09-3S-01E-000-05159-000" (dash-stripped
-- equality), verified against Wakulla's own ArcGIS cadastral layer
-- (services.arcgis.com/yghUoIoA2Cd2cWki/.../Wakulla_Parcels/FeatureServer/0), which returned
-- exactly 1 matching feature with MAP_ACRES=0.49 (consistent with DOR LND_SQFOOT=21,518 sqft).
--
-- Zoning resolved via point-in-polygon spatial query against Wakulla County's OWN official
-- zoning layer (services9.arcgis.com/vAltLjtfYIJc7pDt/.../Zoning_Map/FeatureServer/30,
-- discovered this session -- owned by county planning staff accounts acheek/brandon.geiger)
-- using the parcel's true centroid geometry (not an address-interpolated point, which proved
-- imprecise in this C2/C4/RR1/RR5 zoning mosaic along the highway): CUR_ZONING=C2 (General
-- Commercial). Cross-checked against DOR use code 012 (commercial/mixed-use category, not
-- residential-only) -- consistent, not contradictory.
--
-- Independently adversarially verified (ULTRALOOP protocol): a separate refuter subagent with
-- no access to this reasoning re-fetched all primary sources live and CONFIRMED 5 of 6 checks
-- exactly, found zero factual errors, and explicitly tried and failed to find a plausible
-- alternative zoning reading. The 6th check (verbatim notice text) the refuter could not
-- reproduce on its own tooling (Firecrawl 0 credits, WebFetch/Exa can't render the notice
-- site's SPA) -- but the primary session independently retrieved and quoted that text
-- directly via a working Playwright browser-automation path (search box fill+submit),
-- a different, successful method than what the refuter had available.
--
-- All writes applied live via PostgREST (SUPABASE_SERVICE_ROLE_KEY) during this session --
-- direct psql to the pooler failed with "password authentication failed for user postgres"
-- (environment issue, flagged for next session; REST worked throughout as the fallback).
-- This file is checked in for repo parity / SHIP GATE audit trail; the statements below
-- reproduce those live writes for any session restoring from a fresh database.
--
-- RESULT (live, both before this file's re-application if run twice -- both writes are
-- idempotent: the UPDATE targets one row by primary key predicate, the zoning INSERT would
-- need an existence check on re-run):
--   pencil_dod_evaluate_county('wakulla') BEFORE: E=93.3% FAIL (28/30), I=93.3% FAIL (28/30)
--   pencil_dod_evaluate_county('wakulla') AFTER:  E=96.7% PASS (29/30), I=96.7% PASS (29/30)
--   wakulla is now 10/10 on pencil_dod_evaluate_county -- all of A-J PASS live.
--   2026-TXD-097 remains the sole permanent, correctly-unlinked gap (redeemed tax
--   certificate, no deed ever issued) -- this is why the ceiling is 96.7%, not 100%, and
--   that is expected and correct per canon, not a residual bug.
--   gold_standard_county_status / gold_standard_scoreboard will reflect this on the next
--   scheduled gold_standard_loop() run (not run directly this session per PARALLEL-FLEET
--   RULES -- other shards may be mid-flight). Full 10/10 certification requires a second
--   consecutive daily 10/10 loop run per the standing certify-gate policy.

UPDATE public.multi_county_auctions
SET parcel_id = '09-3S-01E-000-05159-000',
    property_address = '885 WOODVILLE HWY, CRAWFORDVILLE, FL 32327',
    city = 'CRAWFORDVILLE',
    zip = '32327',
    latitude = 30.236995911922662,
    longitude = -84.23064277786379,
    market_value = 177323,
    assessed_value = 177323,
    legal_description = '9-3S-1E P-76-M-75B (DOR NAL S_LEGAL; full metes-and-bounds Parcel 1 in Final Judgment dated 2026-05-06, Case 2025-CA-68, published Notice of Foreclosure Sale, The Wakulla Sun 2026-07-02/07-09)',
    owner_name = 'Carolyn Sherrell'
WHERE case_number = '25-CA-68' AND county = 'wakulla';

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '09-3S-01E-000-05159-000', 1402, 'C2', 'General Commercial District',
       'ZoningWakulla_ArcGIS_dispatch_55e44a55_spatial_centroid_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones
  WHERE parcel_id = '09-3S-01E-000-05159-000' AND jurisdiction_id = 1402
);
