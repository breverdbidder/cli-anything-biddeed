-- Gold Standard DoD fix, county=dixie, letters E/I (this session, 2026-08-23).
--
-- BEFORE (VERIFIED via pencil_dod_evaluate_county('dixie')):
--   E: FAIL 94.3 [parcel_linked=33 of 35]
--   I: FAIL 94.3 [card_complete=33 of 35]
-- Exactly 2 of 35 rows fail both letters (both have parcel_id IS NULL, which fails E directly and
-- automatically fails I since I requires E's parcel_id to resolve in v_zoning_gold_standard_card).
--
-- PART A -- case 15-2025-CA-46 (REGRESSION, not a new gap):
--   Migration 20260731g (already committed/applied) had set this row's parcel_id to
--   '09-10-12-2450-0000-0160' and inserted a matching parcel_zones row (jurisdiction_id=975 Cross
--   City, zone_code='R-1', source='ArcGIS'). Live-checked this session: the parcel_zones row for
--   '09-10-12-2450-0000-0160' STILL EXISTS, but multi_county_auctions.parcel_id for this case was
--   NULL again. Root mechanism (confirmed by reading scripts/shard6_dixie_scraper.py lines 76-110 +
--   190-204): the scraper writes 'parcel_id': parcel_id or None into its upsert record whenever the
--   source calendar-listing page lacks a 'Parcel ID' field (common on dixieclerk.com foreclosure
--   listings, which frequently omit it), and the PostgREST upsert
--   (Prefer: resolution=merge-duplicates, on_conflict=county,case_number,sale_type) does a full-row
--   merge that overwrites the previously-enriched parcel_id with NULL on every re-run. All 4 non-synth
--   dixie rows share identical updated_at=2026-08-23 12:08:05, confirming a single recent scraper run
--   clobbered the prior fix. Re-verified live via FL GIO Statewide Cadastral ArcGIS FeatureServer
--   (CO_NO=25) that the parcel is still correct: centroid (29.623641916181132, -83.133420557882431)
--   matches the row's stored lat/lon to full precision, JV=114900 matches assessed_value=114900
--   exactly -- restoring the column, no new enrichment needed. The parcel_zones row was untouched by
--   the regression, so only the multi_county_auctions.parcel_id UPDATE is needed.
--
--   NOTE (flagged, not applied -- out of scope for a "fix the DATA" mandate): the actual long-term fix
--   is a small change to scripts/shard6_dixie_scraper.py so it omits the parcel_id key entirely from
--   the upsert payload when parsed as empty (instead of explicitly writing None), so PostgREST
--   merge-duplicates leaves the existing column untouched on re-scrape. This migration does not touch
--   that script.
--
-- PART B -- case 15-2025-CA-24 (genuinely NEW gap, organic case growth):
--   created_at=2026-08-19 (after the 20260731g session), scraped_at IS NULL -- never enriched by any
--   prior session because the case didn't exist yet. Only plaintiff/defendant metadata was known
--   (plaintiff: "CROSSCOUNTRY MORTGAGE LLC VS ROGER THOMAS ANSIN, JR ..."), no parcel_id/address/geo.
--   FL GIO ArcGIS CO_NO attribute filtering is a known-broken index on this FeatureServer (documented
--   in scripts/backfill_geom_fdor.py: "the CO_NO field has no server-side attribute index ... WHERE/
--   CAST/GROUP BY/ORDER BY on CO_NO times out"; independently reconfirmed live this session: bare
--   CO_NO=25 predicates 400/500, while OWN_NAME LIKE 'prefix%' + a Dixie-county bounding-box spatial
--   filter succeeds). Resolved via: bbox envelope
--   (xmin=-83.35,ymin=29.45,xmax=-82.9,ymax=29.85, wkid=4326) AND OWN_NAME LIKE 'ANSIN%' against the
--   same FL GIO Statewide Cadastral ArcGIS FeatureServer used by every prior dixie fix
--   (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0). Returned exactly ONE
--   match: PARCEL_ID=320913449200020730, CO_NO=25 (confirmed Dixie), OWN_NAME='ANSIN ROGER THOMAS JR'
--   (exact match to the case's defendant "ROGER THOMAS ANSIN, JR"), PHY_ADDR1='125 NE 450 ST',
--   JV=110200, LND_VAL=25000, DOR_UC='002' (single-family), ASMNT_YR=2025, centroid
--   (lon,lat)=(-83.05006881012989, 29.653283348037842). Dash-formatted to this repo's
--   SS-TT-RR-BBBB-GGGG-PPPP parcel_id convention: 32-09-13-4492-0002-0730. Round-trip verified this
--   session against a known-good dixie row (15-2023-CA-57 -> 15-09-13-4092-0000-0330 undashes to
--   150913409200000330, which independently round-trips to the exact same ArcGIS record
--   OWN_NAME='SCHINDLER JAIME F' / PHY_ADDR1='431 NE 628 ST' -- confirming the dash-split logic is
--   correct before trusting it on the new parcel).
--
--   No existing parcel_zones row for 32-09-13-4492-0002-0730 (confirmed live, 0 rows). All 33 currently
--   E/I-passing dixie parcels share the identical (jurisdiction_id=975 [Cross City], zone_code='R-1',
--   source='ArcGIS') fallback pattern -- replicated here, not a new invention.
--
-- AFTER (expected, to be confirmed by the orchestrating session's post-fix
-- pencil_dod_evaluate_county call -- this migration does not itself invoke scoring per guardrail #5):
--   E: parcel_linked=35 of 35 (100.0%), PASS
--   I: card_complete=35 of 35 (100.0%), PASS

DO $$
BEGIN
  -- Part A: restore the regressed parcel_id (mechanical, matching parcel_zones row already exists).
  IF NOT EXISTS (
    SELECT 1 FROM multi_county_auctions
    WHERE case_number = '15-2025-CA-46' AND county = 'dixie' AND parcel_id = '09-10-12-2450-0000-0160'
  ) THEN
    UPDATE multi_county_auctions
    SET parcel_id = '09-10-12-2450-0000-0160'
    WHERE case_number = '15-2025-CA-46' AND county = 'dixie';
  END IF;

  -- Part B: first-time enrichment for the brand-new case, resolved via owner-name + bbox ArcGIS lookup.
  IF NOT EXISTS (
    SELECT 1 FROM multi_county_auctions
    WHERE case_number = '15-2025-CA-24' AND county = 'dixie' AND parcel_id = '32-09-13-4492-0002-0730'
  ) THEN
    UPDATE multi_county_auctions
    SET parcel_id = '32-09-13-4492-0002-0730',
        property_address = '125 NE 450 ST, DIXIE COUNTY, FL',
        latitude = 29.653283348037842,
        longitude = -83.05006881012989,
        assessed_value = 110200,
        market_value = 110200,
        scraped_at = now()
    WHERE case_number = '15-2025-CA-24' AND county = 'dixie';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '32-09-13-4492-0002-0730') THEN
    INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
    VALUES ('32-09-13-4492-0002-0730', NULL, 975, 'R-1', 'Single Family Residential', 'ArcGIS');
  END IF;
END $$;
