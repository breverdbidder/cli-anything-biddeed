-- Gold Standard shard-1 (dispatch 42aac1fb) continuation:
-- (A) bradford orphan case parcel resolution (flips letter E)
-- (B) okeechobee I completion: Basswood parcel zoning + 2026TD050 address fix

-- ============================================================================
-- PART A: Bradford case 25000439CAAXMX had zero data (no parcel_id, no
-- address). Resolved via Bradford County Property Appraiser owner-name search
-- (playwright, live) matching the BC Telegraph legal-notice metes-and-bounds
-- character-for-character (132.00' x 330.00', Sec 11 T7S R21E, 56x30 2024
-- mobile home). Independently cross-verified against the Bradford Clerk's own
-- "Foreclosure Sale Listings" document (bradfordcounty.app.box.com), which
-- lists this exact case/plaintiff/defendant with a scheduled sale date of
-- 08/13/2026 (not yet occurred) -- consistent with sold_amount remaining NULL.
-- lat/lon, assessed_value, and zone_code were NOT resolvable this session
-- (parcel_id absent from FL GIO under every format tried) and are left NULL --
-- BLANK > WRONG, not fabricated. Card completeness (I) for this row therefore
-- remains incomplete even after this fix; parcel linkage (E) is now complete.
UPDATE multi_county_auctions
SET parcel_id = '00868-0-01200',
    property_address = '7594 SW 130TH ST, STARKE, FL 32091',
    updated_at = now()
WHERE county = 'bradford' AND case_number = '25000439CAAXMX'
  AND parcel_id IS NULL;

-- ============================================================================
-- PART B: Okeechobee I completion.
-- ============================================================================

-- B1: Basswood Inc. Unit No. 6 parcel (case 472025CA000225CAAXMX) already had
-- address/coords/value; only zoning was missing. Confirmed via Okeechobee
-- County Property Appraiser GIS parcel-detail lookup (PIN-based, live), and
-- the lookup method was spot-checked against an existing DB row
-- (1-06-38-36-0A00-00002-0000, zone_code='A') and reproduced it exactly.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '1-05-37-35-0060-00640-0170', 943, 'RSF', 'RESIDENTIAL SINGLE FAMILY',
       'shard1_42aac1fb_continuation/VERIFIED:https://okeechobeegis.com/gis/?PIN=1-05-37-35-0060-00640-0170 (Okeechobee PA GIS parcel-detail lookup, method spot-checked against existing DB row 1-06-38-36-0A00-00002-0000 zone_code=A, reproduced exactly)'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '1-05-37-35-0060-00640-0170' AND jurisdiction_id = 943
);

-- B2: Case 2026TD050 (parcel 1-25-37-35-0070-00060-1760) had no
-- property_address on file. Resolved via 3 independent sources cross-checked
-- this session: the Okeechobee Clerk's own Certificate of Tax Deed
-- Application (case detail + Clerk's Certificate PDF, doc 706425), an
-- address-numbering-gap corroboration against the Property Appraiser's
-- record-search results for the same subdivision block, and an independent
-- third-party aggregator match. Coordinates geocoded from the confirmed
-- address via OpenStreetMap Nominatim (reproduced exactly on independent
-- re-query). market_value and zone_code are NOT set: this parcel_id is
-- confirmed absent from BOTH FL GIO's cadastral roll and the Okeechobee
-- Property Appraiser's own assessment roll (numbering sequence skips directly
-- from suffix ...1740 to ...1770), so no assessed value exists to record, and
-- the zoning lookup endpoint (JS/AJAX) timed out under the session's time
-- budget. Left NULL rather than guessed -- this row remains I-incomplete.
UPDATE multi_county_auctions
SET property_address = '3618 SE 27TH ST, OKEECHOBEE, FL 34974',
    latitude = 27.2192572,
    longitude = -80.7912231,
    updated_at = now()
WHERE county = 'okeechobee' AND case_number = '2026TD050'
  AND parcel_id = '1-25-37-35-0070-00060-1760'
  AND property_address IS NULL;
