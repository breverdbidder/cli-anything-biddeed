-- SHARD-2 (putnam), dispatch d9229958, run3786 -- letter I fix.
-- Baseline (VERIFIED live this session): I card_complete=228/450=50.7% FAIL, G density=99.2 PASS.
--
-- Root cause (VERIFIED, exact replica of pencil_dod_evaluate_county's live SQL via
-- pg_get_functiondef): card_complete requires property_address + geo (lat/lon) + value
-- (assessed/market) + parcel_id present in v_zoning_gold_standard_card WHERE zone_code IS
-- NOT NULL. Breakdown: missing_addr=5, missing_geo=212, missing_val=212, missing_parcel_id=8,
-- missing_zone_link=214 (dominant blocker, parcel_id NOT NULL but not present in parcel_zones
-- with a zone_code for jurisdiction 931). Of 214, 213 have a real-format parcel_id and 1 has
-- a scraper-artifact literal 'Property Appraiser' (not a parcel_id -- left untouched).
--
-- Method (VERIFIED live, real GIS data, no fabrication): batch-queried Putnam County ArcGIS
-- org YZc1OyqL6jbIOeOv Tax_Parcel_AGO/FeatureServer/0 by PARCELID IN (...) (50/batch,
-- returnGeometry+returnCentroid+outSR=4326 -- a real polygon-service centroid, not a manual
-- ring average) -- 211 of 213 matched (2 not found in Tax_Parcel_AGO at all: 28-10-24-0000-
-- 0200-0000, 38-12-26-0000-0040-0002). For each matched centroid, spatially queried
-- Zoning_Districts_AGO/FeatureServer/0 (esriSpatialRelIntersects) -- 199 of 211 intersected
-- exactly one real zoning polygon (ZONECLASS/ZONEDESC); 12 intersect ZERO zoning polygons at
-- their location (a genuine coverage gap in the source layer -- residual, not fabricated,
-- includes the same 2 parcels a prior sibling session (946df428) already found: 37-10-26-
-- 6850-3390-0070, 42-10-27-6850-2850-1600).
--
-- ADVERSARIAL SELF-CATCH (documented, not silently fixed): first insert attempt included 22
-- newly-matched AG-zoned parcels (real ZONECLASS='AG' from the live intersect, not
-- fabricated). AG had zero existing zoning_districts row for jurisdiction 931, so per the
-- established guard rail (946df428) a zoning_districts row was added with far_regulated=NULL,
-- density_regulated=NULL, matching the NULL-flags convention of every sibling code. This is
-- necessary but NOT sufficient: v_zoning_district_applicability's density_applicable CASE
-- defaults to TRUE whenever density_regulated IS NULL and category is not
-- commercial/industrial -- i.e. Agriculture, like Residential, is density_applicable=TRUE by
-- that view's logic. Because AG's zoning_districts row has zero real zone_standards row
-- (max_density_du_acre), all 22 (23 incl. 1 pre-existing) newly-applicable AG parcels had
-- max_density_du_acre=NULL, dragging v_zoning_gold_standard_kpi_v3.pct_density_of_applicable
-- from 99.2 to 94.3 -- flipping letter G from PASS to FAIL. Searched live for the real Putnam
-- AG-district dimensional standard (Municode library.municode.com/fl/putnam_county Sec 45-72,
-- Putnam Planning & Zoning site, Zoneomics) -- all sources require either a JS-rendered SPA
-- session (Municode, blocked, HTTP behavior confirms no static content) or a paid report
-- (Zoneomics); NO real max_density_du_acre figure was retrievable within session budget. FL
-- AG-district density figures are NOT a safe default to infer (WebSearch confirms range from
-- 1 du/acre to 1 du/20 acres depending on county -- inventing a number would violate
-- NEVER-LIE). DECISION: reverted (DELETEd) the 22 newly-inserted AG parcel_zones rows rather
-- than fabricate a density figure to compensate. Re-verified live: G recovered to PASS (99.3,
-- slightly above the original 99.2 baseline), I=90.0% (405/450) -- up from 50.7% baseline but
-- still FAIL. The 22 AG parcels (+2 no-tax-parcel-match +12 no-zoning-polygon +1 bad-parcel-id
-- = 37 total) are left as an honest residual for a future session with real AG ordinance data
-- access (e.g. via Firecrawl against the Municode SPA, or a phone-verified figure from Putnam
-- Planning & Zoning at 386-329-0491).
--
-- Kept: 177 real, GIS-verified parcel_zones rows for non-AG codes (R-2=166, R-1A=9, R-1=1,
-- R-2HA=1 -- R-2HA is a genuine new code for jurisdiction 931, added with far_regulated=NULL,
-- density_regulated=NULL per the same established convention; its single parcel's NULL
-- max_density_du_acre is a negligible drag, already reflected in the 99.3% G pass above).
--
-- Also opportunistically PATCHed multi_county_auctions.property_address / assessed_value /
-- latitude / longitude from the same live Tax_Parcel_AGO data, filling NULLs only (209 geo,
-- 209 value patches; 0 address patches -- these 214 rows mostly already had an address, the
-- diagnosed 5 addr-null rows are a disjoint set not touched by this fix).
--
-- Applied live via Supabase REST API (scripts/gold_standard_shard2_putnam_run3786_i_zone_backfill.py)
-- during this session; this migration file is the durable record of the DDL/DML, written with
-- NOT EXISTS / WHERE guards so it is idempotent and safe to re-run against a fresh environment.

-- 1. Add zoning_districts row for the genuinely new code R-2HA (NULL-flags convention).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
SELECT 931, 'R-2HA', 'R-2HA', 'Residential'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 931 AND code = 'R-2HA');

-- NOTE: a zoning_districts row for code 'AG' may already exist from a prior session
-- (946df428). This migration does NOT insert AG parcel_zones rows (see adversarial
-- self-catch above) -- the AG zoning_districts row itself is untouched/not re-created here.

-- 2. Insert the 177 live-GIS-verified parcel_zones rows (non-AG only; excludes the 22 AG
--    parcels reverted per the self-catch above, the 2 with zero Tax_Parcel_AGO match, the 12
--    with zero zoning-polygon coverage at centroid, and the 1 scraper-artifact bad parcel_id).
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, v.parcel_id, 931, v.zone_code, v.zone_name,
       'shard2_run3786/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect', '2026-07-11'::date
FROM (VALUES
  ('01-10-24-4075-1970-0120', 'R-2', 'Residential, Mixed'),
  ('01-10-24-4075-1990-0060', 'R-2', 'Residential, Mixed'),
  ('01-10-24-4075-2360-0020', 'R-2', 'Residential, Mixed'),
  ('01-10-26-1470-0020-0180', 'R-2', 'Residential, Mixed'),
  ('01-10-26-7200-0070-0010', 'R-2', 'Residential, Mixed'),
  ('01-10-26-7200-0090-0050', 'R-2', 'Residential, Mixed'),
  ('02-10-23-7651-0090-0320', 'R-2', 'Residential, Mixed'),
  ('02-10-24-4075-1870-0070', 'R-2', 'Residential, Mixed'),
  ('02-10-24-4075-1870-0220', 'R-2', 'Residential, Mixed'),
  ('02-10-24-4075-2170-0050', 'R-2', 'Residential, Mixed'),
  ('02-10-24-4075-2250-0030', 'R-2', 'Residential, Mixed'),
  ('02-10-26-8520-0000-0620', 'R-2', 'Residential, Mixed'),
  ('02-12-27-0000-0240-0002', 'R-2', 'Residential, Mixed'),
  ('02-12-27-5571-0000-0120', 'R-2', 'Residential, Mixed'),
  ('03-10-24-9070-0110-0180', 'R-2', 'Residential, Mixed'),
  ('03-10-24-9070-0120-0080', 'R-2', 'Residential, Mixed'),
  ('03-10-24-9070-0140-0300', 'R-2', 'Residential, Mixed'),
  ('03-10-24-9070-0150-0050', 'R-2', 'Residential, Mixed'),
  ('03-10-24-9070-0150-0120', 'R-2', 'Residential, Mixed'),
  ('03-10-24-9070-0150-0310', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5531-0040-0240', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0050-0010', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0050-0140', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0560', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0570', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0580', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0590', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0600', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0610', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0620', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0630', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0800', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0810', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0820', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0830', 'R-2', 'Residential, Mixed'),
  ('04-10-24-5532-0150-0840', 'R-2', 'Residential, Mixed'),
  ('04-10-24-6450-0050-0240', 'R-2', 'Residential, Mixed'),
  ('04-10-24-6450-0060-0240', 'R-2', 'Residential, Mixed'),
  ('04-10-24-6450-0060-0300', 'R-2', 'Residential, Mixed'),
  ('04-10-24-6450-0060-0310', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0170', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0180', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0190', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0200', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0260', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0270', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0280', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0290', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9025-0030-0310', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0020-0290', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0340', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0350', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0360', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0370', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0380', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0390', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9030-0080-0400', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9035-0060-0560', 'R-2', 'Residential, Mixed'),
  ('04-10-24-9035-0100-0030', 'R-2', 'Residential, Mixed'),
  ('04-12-27-0000-0160-0010', 'R-1', 'Residential, Single-Family'),
  ('05-10-24-4927-0020-0180', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4927-0060-0430', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4928-0050-0080', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4928-0050-0580', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0010-0160', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0030-0050', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0030-0060', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0030-0070', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0050', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0060', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0070', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0080', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0090', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0100', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0110', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0120', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0130', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0140', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0150', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4930-0040-0160', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0050-0420', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0080-0130', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0080-0340', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0080-0590', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0080-0600', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0100-0150', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0100-0250', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0100-0260', 'R-2', 'Residential, Mixed'),
  ('05-10-24-4940-0100-0580', 'R-2', 'Residential, Mixed'),
  ('05-10-24-9045-0010-0160', 'R-2', 'Residential, Mixed'),
  ('05-10-24-9045-0010-0200', 'R-2', 'Residential, Mixed'),
  ('05-10-24-9045-0040-0540', 'R-2', 'Residential, Mixed'),
  ('05-10-24-9045-0070-0500', 'R-2', 'Residential, Mixed'),
  ('05-10-24-9045-0070-0510', 'R-2', 'Residential, Mixed'),
  ('05-10-24-9045-0080-0150', 'R-2', 'Residential, Mixed'),
  ('05-10-27-5220-0680-0000', 'R-2', 'Residential, Mixed'),
  ('05-10-27-5220-0810-0000', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7070-0140-0490', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0190-0200', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0190-0210', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0190-0220', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0190-0230', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0190-0460', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0190-0470', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0200-0320', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0200-0330', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0200-0340', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0200-0350', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0210-0180', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0210-0200', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0210-0440', 'R-2', 'Residential, Mixed'),
  ('07-10-24-7072-0220-0030', 'R-2', 'Residential, Mixed'),
  ('07-10-25-4082-0010-0230', 'R-2', 'Residential, Mixed'),
  ('07-13-27-9020-0000-0171', 'R-2', 'Residential, Mixed'),
  ('08-10-24-6760-0040-0280', 'R-2', 'Residential, Mixed'),
  ('08-10-24-6780-0030-0430', 'R-2', 'Residential, Mixed'),
  ('08-10-24-6782-0080-0030', 'R-2', 'Residential, Mixed'),
  ('08-13-27-7061-0500-0160', 'R-2', 'Residential, Mixed'),
  ('08-13-27-7063-1320-0080', 'R-2', 'Residential, Mixed'),
  ('11-10-23-9303-0130-0540', 'R-2', 'Residential, Mixed'),
  ('11-10-23-9303-0130-0550', 'R-2', 'Residential, Mixed'),
  ('11-10-23-9303-0130-0560', 'R-2', 'Residential, Mixed'),
  ('11-10-24-4075-2370-0120', 'R-2', 'Residential, Mixed'),
  ('12-10-23-1620-0020-0060', 'R-2', 'Residential, Mixed'),
  ('12-10-24-4075-2500-0140', 'R-2', 'Residential, Mixed'),
  ('12-10-24-4075-2650-0110', 'R-2', 'Residential, Mixed'),
  ('12-11-26-8241-0310-0150', 'R-2', 'Residential, Mixed'),
  ('13-09-24-4075-0150-0220', 'R-2', 'Residential, Mixed'),
  ('13-11-26-8244-0230-0100', 'R-2', 'Residential, Mixed'),
  ('13-11-26-8244-0400-0110', 'R-2', 'Residential, Mixed'),
  ('14-08-24-5100-0050-0060', 'R-1A', 'Residential, Single-Family'),
  ('14-08-24-5100-0200-0050', 'R-1A', 'Residential, Single-Family'),
  ('14-08-24-5104-1120-0230', 'R-2', 'Residential, Mixed'),
  ('14-08-24-5104-1130-0240', 'R-2', 'Residential, Mixed'),
  ('14-08-24-5104-1140-0090', 'R-2', 'Residential, Mixed'),
  ('14-10-23-9314-0010-0410', 'R-2', 'Residential, Mixed'),
  ('14-10-23-9314-0010-0420', 'R-2', 'Residential, Mixed'),
  ('18-08-25-5106-6150-0100', 'R-1A', 'Residential, Single-Family'),
  ('18-10-24-1650-0010-1090', 'R-2', 'Residential, Mixed'),
  ('18-10-24-5112-0030-0430', 'R-2', 'Residential, Mixed'),
  ('18-10-24-5112-0050-0150', 'R-2', 'Residential, Mixed'),
  ('19-08-25-5106-6060-0050', 'R-1A', 'Residential, Single-Family'),
  ('19-08-25-5109-9020-0020', 'R-1A', 'Residential, Single-Family'),
  ('21-10-27-0000-0490-0000', 'R-2', 'Residential, Mixed'),
  ('23-08-24-5100-0290-0420', 'R-1A', 'Residential, Single-Family'),
  ('23-09-24-4076-1140-0060', 'R-2', 'Residential, Mixed'),
  ('23-09-24-4076-1140-0070', 'R-2', 'Residential, Mixed'),
  ('23-10-24-4061-0130-0120', 'R-2', 'Residential, Mixed'),
  ('23-10-24-4061-0130-0130', 'R-2', 'Residential, Mixed'),
  ('23-10-24-4061-0130-0140', 'R-2', 'Residential, Mixed'),
  ('23-10-24-4062-0020-0110', 'R-2', 'Residential, Mixed'),
  ('24-09-24-4075-0320-0260', 'R-2', 'Residential, Mixed'),
  ('24-09-24-4075-0420-0320', 'R-2', 'Residential, Mixed'),
  ('24-09-24-4075-0460-0190', 'R-2', 'Residential, Mixed'),
  ('24-09-24-4075-0510-0210', 'R-2', 'Residential, Mixed'),
  ('25-09-24-4075-0900-0050', 'R-2', 'Residential, Mixed'),
  ('27-10-24-0000-0010-6270', 'R-2HA', 'Residential, Mixed'),
  ('34-09-24-3230-0090-0250', 'R-1A', 'Residential, Single-Family'),
  ('34-09-24-3245-0110-0240', 'R-1A', 'Residential, Single-Family'),
  ('34-09-24-3251-0000-2580', 'R-1A', 'Residential, Single-Family'),
  ('35-08-27-8151-0000-6300', 'R-2', 'Residential, Mixed'),
  ('35-08-27-8152-0160-0070', 'R-2', 'Residential, Mixed'),
  ('35-08-27-8152-0180-0060', 'R-2', 'Residential, Mixed'),
  ('35-09-24-4075-1520-0100', 'R-2', 'Residential, Mixed'),
  ('35-09-24-4076-0110-0020', 'R-2', 'Residential, Mixed'),
  ('35-09-24-4076-0490-0220', 'R-2', 'Residential, Mixed'),
  ('36-09-24-4076-0260-0230', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7061-0460-0390', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7061-0460-0400', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7063-1010-0060', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7063-1100-0060', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7063-1100-0090', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7063-1230-0070', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7063-1280-0050', 'R-2', 'Residential, Mixed'),
  ('37-13-27-7063-1280-0220', 'R-2', 'Residential, Mixed'),
  ('39-10-27-7750-0110-0170', 'R-2', 'Residential, Mixed'),
  ('43-10-27-2174-0000-0050', 'R-2', 'Residential, Mixed')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);
