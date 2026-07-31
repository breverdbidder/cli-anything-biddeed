-- Gold Standard shard-5 seminole C/D/I fix, 2026-07-31.
--
-- Context (VERIFIED live via pencil_dod_evaluate_county('seminole'), 2026-07-31):
--   C BEFORE: 90.2% (matched_clean=111 of 123) -- FAIL (need >=95%)
--   D BEFORE: 90.2% (matched_any=111 of 123)   -- FAIL (need >=95%)
--   I BEFORE: 88.6% (card_complete=109 of 123) -- FAIL (need >=95%)
--
-- ── C/D GAP (12 rows, all parity_status IS NULL) ────────────────────────────────
--
-- All 12 rows are fresh calendar_sweep_mca_v3 ingest rows (2026-07-25 / 2026-07-29)
-- never run through parity reconciliation. This migration independently verifies
-- each against a live tier1 source (NOT the MCA row's own scraped data -- that
-- would be self-referential) and stamps parity_status/parity_source/parity_confidence.
--
-- 1. Foreclosure row: 2025CA001015
--    SOURCE (VERIFIED): pipeline.tier1_today, source_platform='realforeclose',
--      scraped_at=2026-07-30 21:18:03 UTC. Row confirms case_number=2025CA001015,
--      parcel_id=18-20-31-509-0000-0340, property_address="1810 PINE OAK TRL,
--      SANFORD, FL- 32773", assessed_value=220112.00, auction_date=2026-08-18 --
--      exact match to the MCA row. parity_source follows the existing plain
--      'tier1_realforeclose_seminole' naming convention already live for this county
--      (confirmed via: SELECT DISTINCT parity_source FROM multi_county_auctions
--      WHERE lower(county)='seminole' AND parity_source LIKE 'tier1%').
--
-- 2. Tax deed rows (11), all auction_date=2026-10-15:
--    SOURCE (VERIFIED): https://seminole.realtdm.com/public/cases/list -- the
--      Seminole County Clerk's own public "REAL TDM" tax-deed case search system
--      (independent of realtaxdeed.com / RealAuction, genuinely separate source
--      from the MCA row's own calendar_sweep_mca_v3 ingest). Public POST search
--      by filterCaseNumber (no auth required, isPublic=1 flag). Each of the 11 case
--      numbers returned "Found 1 Result" with a CASE # exactly matching, Status
--      ACTIVE, Parcel Number exactly matching, Sale Date "Oct 15, 2026":
--        20260004/2024-001492 -> Parcel 10-21-29-528-1300-1030 (confirmed)
--        20260005/1716-2024   -> Parcel 11-21-31-504-0B00-0150 (confirmed)
--        20260008/2024-002188 -> Parcel 14-21-29-5SB-0200-2080 (confirmed)
--        20260009/2024-002335 -> Parcel 15-21-29-509-1700-0080 (confirmed)
--        20260010/2024-002745 -> Parcel 17-21-29-5BG-0000-018A (confirmed)
--        20260014/2024-3184   -> Parcel 20-20-30-502-0C00-0090 (confirmed)
--        20260015/2024-003544 -> Parcel 21-21-32-5CF-4400-0080 (confirmed)
--        20260025/2024-004214 -> Parcel 25-19-30-5AG-0X00-0050 (confirmed; address
--          genuinely "N/A" from source but case+parcel independently verified, so
--          C/D parity is still legitimately confirmable even though I remains blocked)
--        20260026/2024-5114   -> Parcel 31-20-30-501-0000-0560 (confirmed)
--        20260029/2024-006503 -> Parcel 36-19-30-542-0000-013A (confirmed)
--        20260035/2024-003228 -> Parcel 20-21-30-503-0F00-0030 (confirmed)
--      Also cross-checked against the public (no-login) RealTaxDeed PREVIEW page
--      for AuctionDate=10/15/2026 (https://seminole.realtaxdeed.com/index.cfm?
--      zaction=AUCTION&zmethod=PREVIEW&AuctionDate=10/15/2026, fetched with a
--      standard browser User-Agent), whose embedded #ALB auction-item-ID list
--      contains exactly 11 numeric item IDs -- matching count for this date,
--      corroborating (though not individually resolving without login) the
--      realtdm.com per-case confirmation above.
--    parity_source uses the existing 'tier1:<harvest>:<sale_type>:<date>' naming
--      convention already live for this county, with harvest tag
--      'realtdm_public_cases_list' (new source name, session-scoped and honest --
--      distinct from the existing ajax_harvest tags which are RealForeclose/
--      RealTaxDeed AJAX scrapes, not this Clerk case-search verification) and
--      today's verification date 2026-07-31.
--
-- ── I GAP (14 rows total; this migration resolves 1 of 14) ─────────────────────
--
-- Read supabase/migrations/20260725_gold_standard_seminole_i_card_completeness.sql
-- first per dispatch instructions. That migration fixed 4 of an earlier 8-row gap
-- (3 of those 4 -- 20260026/2024-5114, 20260014/2024-3184, 20260005/1716-2024 --
-- are CONFIRMED still card_complete this session, no regression, not re-touched).
--
-- Fixed (1 row):
--
--   2025CA001015, parcel_id 18-20-31-509-0000-0340 (1810 Pine Oak Trl, Sanford).
--   Already had property_address + assessed_value from the tier1_today source
--   above. Missing: latitude/longitude and a parcel_zones link.
--   SOURCE for lat/lon (VERIFIED): US Census Bureau geocoder
--     (geocoding.geo.census.gov/geocoder/locations/address), free public
--     government address-point data, same method as the 2026-07-25 migration.
--     Query: street="1810 PINE OAK TRL", city="SANFORD", state=FL, zip=32773.
--     Response matchedAddress: "1810 PINE OAK TRL, SANFORD, FL, 32773",
--     coordinates: y=28.756332560668, x=-81.259162242071.
--   SOURCE for zoning (VERIFIED): https://scpafl.org/search/parcels/details/?PID=18203150900000340
--     (Seminole County Property Appraiser, live parcel lookup, fetched 2026-07-31)
--     quoted: "Property Address: 1810 Pine Oak Trail, Sanford, FL 32773 | Market
--     Value: $219,256 | Assessed Value: $219,256 | Zoning Code: PD | Tax District: Sanford"
--   Zone code PD already exists in zoning_districts for jurisdiction_id=904 (City
--   of Sanford) as id=6329, with density_regulated=false explicitly set (confirmed
--   live: zone_standards row id=4596 has all standards intentionally null, sourced
--   comment explains Sanford PD has no fixed base-code density -- set per individual
--   Master/Final Development Plan, same convention already accepted for this exact
--   district in the 2026-07-11 migration). Reusing this district is zero G-risk:
--   density_regulated=false means this parcel is EXCLUDED from the G
--   pct_density_of_applicable denominator entirely, so this reuse cannot regress G
--   under any circumstance -- the safest possible pattern, identical in kind to the
--   20-20-30-502-0C00-0090/R-1/636 reuse in the 2026-07-25 migration.
--
-- GENUINELY BLOCKED this session (13 of 14 I-gap rows remain unresolved):
--
--   - 20260057/2024-003818 (R-4, Altamonte Springs): fresh check this session
--     (scpafl.org PID lookup, re-fetched 2026-07-31) confirms zoning_code=R-4,
--     tax_district=Altamonte, and explicitly returns NO Activity Center / overlay
--     / FLU designation data -- identical finding to the 2026-07-25 session. R-4
--     density in the Altamonte Springs LDC is Activity-Center-specific and cannot
--     be confirmed applicable to this parcel without an overlay determination this
--     session could not obtain (no Altamonte Springs GIS ArcGIS REST endpoint
--     found; library.municode.com returned 403). Per HARD GUARDRAILS, no density
--     number is fabricated. Value fields for this parcel are already populated
--     from the prior migration; only the zone link remains blocked.
--
--   - 2025CA000629 (parcel_id='SYN-SEM-2025CA000629', synthetic placeholder),
--     2025CA002115 (parcel_id='ALCOHOLIC LICENSE'),
--     2025CA000060 (parcel_id='MULTIPLE PARCELS'):
--     re-confirmed blocked this session -- seminoleclerk.org docket search
--     returned a TLS certificate error ("unable to verify the first certificate")
--     to WebFetch this session; no new independent source found. Status unchanged
--     from 2026-07-25 findings (synthetic/garbage parcel_ids, no real single-parcel
--     identity resolvable).
--
--   - 2024CA001701 (parcel_id='Property Appraiser' garbage artifact, but real
--     address "250 RAINTREE DR, CASSELBERRY, FL- 32707" already geocoded to
--     lat=28.652447454337/lon=-81.306917336264, assessed_value=239027 populated
--     from a prior session): attempted the deferred scpafl.org address-based PID
--     lookup this session. Census geocoder re-confirmed the coordinates match the
--     row's existing values (independent cross-check, no discrepancy). However
--     scpafl.org's address-search UI (/search/parcels) is a client-JS-driven page
--     that does not expose a WebFetch-navigable address->PID query path, and the
--     site went fully unreachable (connect ECONNREFUSED) for repeated direct-PID
--     lookups partway through this session (transient outage, confirmed by retrying
--     a previously-successful PID lookup that also started failing). FL GIO
--     ArcGIS REST spatial/attribute query attempts (PARCEL_ID exact match,
--     PHY_ADDR1 exact match) returned empty feature sets / 400 invalid-parameter
--     errors this session -- query syntax not resolved within time-box. No PID
--     obtained; deferred again to a future session with working scpafl.org access
--     or Casselberry-specific GIS.
--
--   - 20260008/2024-002188, 20260009/2024-002335, 20260010/2024-002745,
--     20260015/2024-003544, 20260029/2024-006503, 20260035/2024-003228,
--     20260026's value/geo already fixed (07-25) with no zone attempt needed here,
--     and case 20260025/2024-004214 (address is genuinely "N/A" from source --
--     cannot geocode or zone-link an incomplete address):
--     These 7 tax_deed rows (excluding 20260025, which is address-incomplete and
--     left blocked) were slated for the identical scpafl.org PID-lookup +
--     Census-geocoder + jurisdiction-reuse methodology used successfully for
--     2025CA001015 above. scpafl.org became unreachable (connect ECONNREFUSED)
--     partway through this session before these 7 PID lookups could be completed,
--     and repeated retries over several minutes did not recover access. Per HARD
--     GUARDRAILS, no address/value/zone data is fabricated for these rows.
--     Deferred to a future session once scpafl.org access is confirmed working.
--
-- Safety summary: this migration performs ZERO new zoning_districts/zone_standards
-- inserts (the one I-fix reuses an existing, already-verified, density_regulated=
-- false district), so it cannot regress G under any circumstance.

SET statement_timeout = 0;

-- ── 1. Diagnostic before update ─────────────────────────────────────────────────
DO $$
DECLARE
  v_before jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_before;
  RAISE NOTICE 'Seminole BEFORE C: %', v_before->'C';
  RAISE NOTICE 'Seminole BEFORE D: %', v_before->'D';
  RAISE NOTICE 'Seminole BEFORE I: %', v_before->'I';
END $$;

-- ── 2. C/D fix: foreclosure row 2025CA001015 (VERIFIED via pipeline.tier1_today) ─
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_seminole',
    parity_confidence = 0.95
WHERE lower(county) = 'seminole'
  AND case_number = '2025CA001015'
  AND parcel_id = '18-20-31-509-0000-0340'
  AND parity_status IS NULL;

-- ── 3. C/D fix: 11 tax_deed rows (VERIFIED via seminole.realtdm.com/public/cases/list) ─
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:realtdm_public_cases_list:tax_deed:2026-07-31',
    parity_confidence = 0.95
WHERE lower(county) = 'seminole'
  AND parity_status IS NULL
  AND sale_type = 'tax_deed'
  AND case_number IN (
    '20260004/2024-001492',
    '20260005/1716-2024',
    '20260008/2024-002188',
    '20260009/2024-002335',
    '20260010/2024-002745',
    '20260014/2024-3184',
    '20260015/2024-003544',
    '20260025/2024-004214',
    '20260026/2024-5114',
    '20260029/2024-006503',
    '20260035/2024-003228'
  );

-- ── 4. I fix: 2025CA001015 -- geo + zone link (VERIFIED scpafl.org + Census geocoder) ─
UPDATE multi_county_auctions
SET latitude = 28.756332560668,
    longitude = -81.259162242071
WHERE lower(county) = 'seminole'
  AND case_number = '2025CA001015'
  AND parcel_id = '18-20-31-509-0000-0340'
  AND latitude IS NULL;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '18-20-31-509-0000-0340', 904, 'PD', 'gold_standard_shard5_seminole_i_20260731_scpafl_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  JOIN jurisdictions j ON j.id = pz.jurisdiction_id
  WHERE pz.parcel_id = '18-20-31-509-0000-0340' AND j.county ILIKE '%seminole%'
);

-- ── 5. Diagnostic after update ──────────────────────────────────────────────────
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_after;
  RAISE NOTICE 'Seminole AFTER C: %', v_after->'C';
  RAISE NOTICE 'Seminole AFTER D: %', v_after->'D';
  RAISE NOTICE 'Seminole AFTER I: %', v_after->'I';
  RAISE NOTICE 'Seminole AFTER G (regression check): %', v_after->'G';
  RAISE NOTICE 'Seminole AFTER FULL: %', v_after;
END $$;
