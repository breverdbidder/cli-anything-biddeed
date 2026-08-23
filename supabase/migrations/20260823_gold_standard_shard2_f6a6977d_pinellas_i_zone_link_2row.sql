-- Gold Standard shard-2 (dispatch f6a6977d), pinellas letter I.
--
-- BASELINE (VERIFIED live via pencil_dod_evaluate_county, this session):
--   I FAIL 94.3% (card_complete=415 of 440)
--
-- INVESTIGATION (VERIFIED live, this session):
-- The 25-row I gap decomposes into two disjoint buckets:
--
--   (a) 17 rows have a real parcel_id + address + geo + value, but NO
--       matching zone_code row in v_zoning_gold_standard_card. Checked
--       these 17 parcel_ids directly against public.parcel_zones -- ZERO
--       exist there (not a join-key/format mismatch: same STRAP-style
--       18-digit parcel_id format is used on both sides, confirmed by
--       direct equality AND substring LIKE checks). Sized the true
--       jurisdiction coverage:
--         Largo (jurisdiction_id=859): 23 zoning_districts rows exist
--           (ordinance catalog was scraped) but 0 parcel_zones rows (no
--           parcel-to-zone GIS linkage has ever been run) -- 8 of the 17
--           gap rows are in Largo.
--         Gulfport (jurisdiction_id=1099): 0 districts AND 0 parcel_zones
--           -- 1 of the 17 gap rows.
--         Remaining 8 rows (Palm Harbor/unincorporated, Pinellas Park,
--         Clearwater, Seminole) fall inside otherwise-covered jurisdictions
--         but are individual unlinked parcels within them.
--       This matches and re-confirms the IDENTICAL finding already made
--       and documented in scripts/pinellas_i_zoning_geo_shard1_3ce988ac.py
--       (dispatch 3ce988ac, 2026-08-14): "Largo, Pinellas Park, and
--       Gulfport ... no discoverable public ArcGIS REST zoning endpoint
--       for incorporated Largo/Pinellas Park/Gulfport specifically."
--       CONCLUSION: genuine ingestion-coverage gap (Largo/Gulfport have no
--       parcel-level zoning GIS layer available), NOT a fixable join
--       issue. Out of scope for a single session per the G-letter
--       playbook precedent (building a full parcel-to-zone spatial join
--       pipeline for these jurisdictions is separate scoped work).
--       LEFT UNTOUCHED THIS SESSION -- residual, documented below.
--
--   (b) ~8 rows fail on ordinary address/geo/value/parcel gaps. Of these,
--       2 were resolved with REAL, VERIFIED Pinellas County Property
--       Appraiser (PCPAO) parcel data, live this session:
--
--       1. case_number=522025CC010155XXCOCO ("7803 46TH AVE NORTH # 114,
--          ST PETERSBURG, FL- 33709"). Matched via
--          egis.pinellas.gov/gis/rest/services/PublicWebGIS/Parcels/
--          MapServer/1, LEGAL field "MELODY GARDENS MOBILE HOME PARK
--          (UNREC) LOT 114" -- unambiguous match to the "# 114" unit
--          suffix. STRAP=163106571300001140, TAXABLE_VALUE=47144,
--          LAND_VALUE=31450, IMP_VALUE=14164. Real polygon centroid
--          computed from the returned ring (outSR=4326):
--          lat=27.81485092953524, lon=-82.74586132934253. Point-in-
--          polygon against PublicWebGIS/Municipalities/MapServer/0
--          confirms UNINCORPORATED (jurisdiction_id=635). Point-in-
--          polygon against PublicWebGIS/Landuse_Zoning/MapServer/1
--          returns ZONECLASS=RMH ("Mobile Home Residential"). RMH already
--          exists as a zoning_districts catalog row for jurisdiction_id
--          635 (id=13606) -- no new catalog row fabricated. This row now
--          has address+geo+value+parcel+zone_code all real -- full I pass.
--          Old values overwritten (both were clearly generic placeholders,
--          not real data): parcel_id NULL, latitude/longitude=27.9/-82.72
--          (this exact lat/lon pair repeats across many other unrelated
--          rows -- a fallback placeholder, not a real geocode),
--          assessed_value=150000 (a flat round number repeated across
--          several other unrelated rows in this same gap set).
--
--       2. case_number=522025CA006711XXCICI ("3505 GULF BLVD SOUTH,
--          ST PETE BEACH, FL- 33706"). Matched via the same Parcels
--          MapServer/1 layer, SITE_ADDRESS='3505 GULF BLVD',
--          SITE_CITY='ST PETE BEACH' -- single unambiguous match.
--          STRAP=163207218520080030, TAXABLE_VALUE=765000,
--          LAND_VALUE=752362, IMP_VALUE=7852. Real centroid:
--          lat=27.71057682219889, lon=-82.73691156280239. Point-in-
--          polygon confirms jurisdiction ST PETE BEACH. St Pete Beach has
--          ZERO zoning_districts rows and ZERO parcel_zones rows
--          countywide (same structural pattern as Largo/Gulfport above) --
--          no zoning source available for this jurisdiction. This row is
--          now address+geo+value+parcel complete but STILL FAILS the I
--          zone_code sub-condition -- genuine structural residual, left
--          as parity_status/zone unlinked, not forced to pass.
--
--       Old parcel_id for this row was the literal garbage string
--       'Property Appraiser' (not a real parcel id) -- overwritten with
--       the real STRAP found above.
--
--   NOT resolved this session (re-confirmed structurally blocked, same
--   finding as the 2026-08-14 session):
--     - 522023CA006219XXCICI: parcel_id='PERSONAL PROPERTY' -- a personal
--       property foreclosure with no titled real-estate parcel to look up.
--       Not a data gap; a case-type characteristic.
--     - 522019CA002273XXCICI, 522025CA000532XXCICI, 522025CA003843XXCICI,
--       522025CA006625XXCICI: NULL or unusable address, no parcel_id.
--       Attempted live re-scrape of the primary source
--       (pinellas.realforeclose.com/index.cfm?...&AID=<id>) for all 4 --
--       site returned HTTP 503 (bot-protected, requires JS) to both
--       WebFetch and a browser-UA curl. No fabricated substitute written.
--       Resolving these needs either a headless-browser session against
--       realforeclose.com or a Clerk docket lookup -- out of scope this
--       pass, re-confirmed identical to the prior 2026-08-14 finding.
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county, this session):
--   I: card_complete 415 -> 416 of 440 (94.3% -> 94.5%). Still FAIL
--      (threshold 95% = 418/440). Real, honest, partial improvement --
--      does not flip the letter given the 17-row Largo/Gulfport
--      structural-ceiling bucket plus the remaining 5 no-address/
--      personal-property rows plus the St Pete Beach zone gap on
--      522025CA006711XXCICI.
--   E: parcel_linked 434 -> 435 of 440 (98.6% -> 98.9%) -- incidental
--      side effect of the parcel_id backfill on 522025CC010155XXCOCO and
--      522025CA006711XXCICI (E only requires parcel_id NOT NULL, already
--      PASS before and after, threshold 95%).
--
-- No fabricated case numbers, parcel IDs, addresses, coordinates, or
-- values anywhere in this migration -- every value above traces to a live
-- egis.pinellas.gov ArcGIS REST query, pasted in this comment block.

-- Idempotent mirror of the live UPDATEs run this session.

UPDATE public.multi_county_auctions
SET parcel_id = '163207218520080030',
    latitude = 27.71057682219889,
    longitude = -82.73691156280239,
    assessed_value = 765000,
    market_value = 765000
WHERE county = 'pinellas'
  AND case_number = '522025CA006711XXCICI'
  AND (parcel_id IS DISTINCT FROM '163207218520080030');

UPDATE public.multi_county_auctions
SET parcel_id = '163106571300001140',
    latitude = 27.81485092953524,
    longitude = -82.74586132934253,
    assessed_value = 47144,
    market_value = 47144
WHERE county = 'pinellas'
  AND case_number = '522025CC010155XXCOCO'
  AND (parcel_id IS DISTINCT FROM '163106571300001140');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '163106571300001140', 635, 'RMH', 'Mobile Home Residential',
       'egis_pinellas_gov_landuse_zoning_verified_20260823'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '163106571300001140'
);
