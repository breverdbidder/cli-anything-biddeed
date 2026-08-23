-- Gold Standard shard-5 (dispatch 79ee1554): lake county E (parcel linkage) + I (card completeness) fix.
--
-- Diagnosis: 11 rows in multi_county_auctions for county='lake' had ONLY case_number +
-- auction_date + sale_type='foreclosure' from data_source='lake_clerk_foreclosure_calendar_v1'
-- (no property_address, no parcel_id, no value). realforeclose.com AJAX feed returned 0 results
-- for all 7 target auction dates (confirmed dead end, do not retry with same method).
--
-- Pivot: Lake County Clerk foreclosure calendar (foreclosurecalendar.lakecountyclerkfl.gov)
-- exposes a per-sale detail page (/sale_details.aspx?id=N) with case number + plaintiff +
-- defendant names (still no property address). Cross-referenced defendant name against the
-- Lake County Property Appraiser ArcGIS FieldMap layer
-- (gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0), which
-- exposes OwnerName + PropertyAddress + TotalJustValue + geometry directly queryable.
--
-- Only accepted matches where full first+last name matched EXACTLY ONE parcel (to avoid
-- false-positive owner-name collisions). Of 10 resolvable-defendant cases (2024CA002312 had
-- no calendar entry to pull a defendant from -- already auction_status='cancelled', updated by
-- another process today, genuinely bare, left untouched), only 2 produced a unique exact match:
--   2024CA000927 (FLAGSTAR BANK vs JOSHUA VASQUEZ, ET AL) -> VASQUEZ JOSHUA A AND SASHA RUIZ,
--     6968 PERCH HAMMOCK LOOP, parcel 052225010000001900, TotalJustValue $436,486
--   2025CA002791 (SELENE FINANCE LP vs SCOTT NEW, ET AL) -> NEW SCOTT & ASHTIN,
--     31546 SUMMIT ST, parcel 251927050002301300, TotalJustValue $145,054
-- Coordinates taken as polygon centroid of ArcGIS geometry (outSR=4326), both plausible
-- Lake County FL coordinates (28.6N/-81.8W and 28.8N/-81.6W respectively).
--
-- The remaining 8 E-gap rows (2023CA000367 corporate-vs-corporate BUILD REI LLC vs PRIDE
-- FUNDING LLC, 2025CA001082, 2025CA001590 JULIE JEFFERSON, 2025CA001729 TIFFANY CARTWRIGHT,
-- 2025CA002454 SARAH BOYD, 2025CC005329 PHILLIP MAMMON [HOA lien], 2025CC010839 VALERIE ZAYAS
-- [HOA lien], 2026CA000560 MARYLINDA LABARCA) returned ZERO or multiple-ambiguous owner-name
-- matches on the ArcGIS layer -- left NULL rather than fabricated. See session report for the
-- exact query strings tried per case.

BEGIN;

-- 2024CA000927: FLAGSTAR BANK vs JOSHUA VASQUEZ, ET AL
UPDATE multi_county_auctions
SET property_address = '6968 PERCH HAMMOCK LOOP',
    parcel_id = '052225010000001900',
    latitude = 28.60299001024558,
    longitude = -81.84170678520925,
    geo_source = 'parcel_centroid',
    assessed_value = 436486,
    assessed_value_source = 'lake_county_property_appraiser_gis_2026-08-23'
WHERE case_number = '2024CA000927'
  AND lower(county) = 'lake'
  AND parcel_id IS NULL;

-- 2025CA002791: SELENE FINANCE LP vs SCOTT NEW, ET AL
UPDATE multi_county_auctions
SET property_address = '31546 SUMMIT ST',
    parcel_id = '251927050002301300',
    latitude = 28.80901600316537,
    longitude = -81.5668656513802,
    geo_source = 'parcel_centroid',
    assessed_value = 145054,
    assessed_value_source = 'lake_county_property_appraiser_gis_2026-08-23'
WHERE case_number = '2025CA002791'
  AND lower(county) = 'lake'
  AND parcel_id IS NULL;

COMMIT;
