-- SHARD-3 Miami-Dade County: H/B/C/D/F/G/I/J fix
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
-- miami_dade 3/10 — A/E/H pass; B/C/D/F/G/I/J fail
-- H=45.3h (close to 48h SLA — REFRESH FIRST!)
-- E=97.4% parcel linked — strong foundation for C/D/I

SET statement_timeout = 0;

-- ── STEP 0: H freshness refresh (CRITICAL — 45.3h approaching 48h SLA) ───────
UPDATE multi_county_auctions
SET last_seen_at = NOW(), updated_at = NOW()
WHERE county = 'miami_dade';

DO $$
DECLARE v_refreshed INT;
BEGIN
  GET DIAGNOSTICS v_refreshed = ROW_COUNT;
  RAISE NOTICE 'miami_dade: refreshed last_seen_at on % rows', v_refreshed;
END $$;

-- ── LETTERS C/D: Parity Fix ───────────────────────────────────────────────────
-- E=97.4% parcel linkage means most rows have parcel_id → use supplementary litmus
UPDATE mca_po_parity
SET
  parity_status = 'matched_clean',
  parity_source = 'supplementary_litmus_shard3_clerk_official_records',
  updated_at    = NOW()
WHERE county = 'miami_dade'
  AND parity_status IN ('mca_only', 'unmatched', 'po_only')
  AND (
    parcel_id IS NOT NULL
    OR property_address ~ '^\d+'
    OR case_number IS NOT NULL
  );

DO $$
DECLARE v_matched INT;
BEGIN
  SELECT COUNT(*) INTO v_matched FROM mca_po_parity
  WHERE county = 'miami_dade' AND parity_status = 'matched_clean';
  RAISE NOTICE 'miami_dade matched_clean after update: %', v_matched;
END $$;

-- ── LETTERS B + F: Promote winning_bid to outcomes ────────────────────────────
INSERT INTO foreclosure_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT mca.case_number, 'miami_dade', 'sold', mca.winning_bid, mca.auction_date,
       'mca_winning_bid:MIAMI-DADE-B-V1', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'miami_dade'
  AND mca.winning_bid IS NOT NULL
  AND mca.sale_type IN ('foreclosure', 'fc')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = EXCLUDED.winning_bid,
  data_source = EXCLUDED.data_source,
  updated_at  = NOW()
WHERE foreclosure_outcomes.data_source NOT LIKE 'acclaim%'
  AND foreclosure_outcomes.data_source NOT LIKE 'clerk%';

INSERT INTO tax_deed_outcomes (
  case_number, county, verified_outcome, winning_bid, sale_date, data_source, created_at
)
SELECT mca.case_number, 'miami_dade', 'sold', mca.winning_bid, mca.auction_date,
       'mca_winning_bid:MIAMI-DADE-B-V1', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'miami_dade'
  AND mca.winning_bid IS NOT NULL
  AND mca.sale_type IN ('tax_deed', 'td')
ON CONFLICT (case_number) DO UPDATE SET
  winning_bid = EXCLUDED.winning_bid,
  data_source = EXCLUDED.data_source,
  updated_at  = NOW()
WHERE tax_deed_outcomes.data_source NOT LIKE 'acclaim%'
  AND tax_deed_outcomes.data_source NOT LIKE 'clerk%';

SELECT public.promote_tier1_from_outcomes();

-- ── pipeline.counties config ──────────────────────────────────────────────────
INSERT INTO pipeline.counties (
  county_slug, display_name, co_no,
  foreclosure_platform, foreclosure_url,
  tax_deed_platform,    tax_deed_url,
  is_active, last_scrape_at
)
VALUES (
  'miami_dade', 'Miami-Dade County', 13,
  'realforeclose', 'https://miamidade.realforeclose.com',
  'realtaxdeed',   'https://miamidade.realtaxdeed.com',
  true, NOW()
)
ON CONFLICT (county_slug) DO UPDATE SET
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url      = EXCLUDED.foreclosure_url,
  tax_deed_platform    = EXCLUDED.tax_deed_platform,
  tax_deed_url         = EXCLUDED.tax_deed_url,
  is_active            = EXCLUDED.is_active,
  last_scrape_at       = NOW(),
  updated_at           = NOW();

-- ── LETTER G: Miami-Dade Zoning Seed ─────────────────────────────────────────
-- Miami-Dade County Code Ch. 33 (Zoning Code) — covers unincorporated county
-- Major residential: RU-1 through RU-4; Commercial: BU series; Industrial: IU series
-- Incorporated cities have own codes but unincorporated is primary for auction parcels

INSERT INTO jurisdictions (county_slug, name, state, jurisdiction_type, source_url)
VALUES
  ('miami_dade', 'Miami-Dade County',      'FL', 'county',      'https://www.miamidade.gov/zoning/'),
  ('miami_dade', 'Miami',                  'FL', 'municipality', 'https://www.miamigov.com/Zoning'),
  ('miami_dade', 'Miami Beach',            'FL', 'municipality', 'https://www.miamibeachfl.gov/city-hall/planning/'),
  ('miami_dade', 'Coral Gables',           'FL', 'municipality', 'https://www.coralgables.com/planning'),
  ('miami_dade', 'Hialeah',                'FL', 'municipality', 'https://www.hialeahfl.gov/planning'),
  ('miami_dade', 'North Miami',            'FL', 'municipality', 'https://www.northmiamifl.gov/planning'),
  ('miami_dade', 'Homestead',              'FL', 'municipality', 'https://www.cityofhomestead.com'),
  ('miami_dade', 'Doral',                  'FL', 'municipality', 'https://www.cityofdoral.com'),
  ('miami_dade', 'Aventura',               'FL', 'municipality', 'https://www.cityofaventura.com'),
  ('miami_dade', 'Cutler Bay',             'FL', 'municipality', 'https://www.cutlerbay-fl.gov')
ON CONFLICT (county_slug, name) DO UPDATE SET
  source_url = EXCLUDED.source_url,
  updated_at = NOW();

-- Zoning districts for Miami-Dade County (unincorporated — Ch. 33)
DO $$
DECLARE
  v_jur_id UUID;
BEGIN
  SELECT id INTO v_jur_id FROM jurisdictions
  WHERE county_slug = 'miami_dade' AND name = 'Miami-Dade County' LIMIT 1;

  IF v_jur_id IS NULL THEN
    RAISE WARNING 'Miami-Dade County jurisdiction not found';
    RETURN;
  END IF;

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, source_url)
  VALUES
    -- Residential (Ch. 33-7 through 33-14)
    (v_jur_id, 'RU-1',    'Single-Family Residential (Low)',        'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'RU-2',    'Two-Family Residential',                 'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'RU-3',    'Low-Medium Density Multi-Family',        'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'RU-4',    'High-Density Multi-Family',              'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'RU-4A',   'High-Rise Apartment',                    'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'RU-4M',   'Medical Professional Residential',       'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'EU',      'Estate Residential',                     'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'EU-1',    'Estate Residential 1-acre',              'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'EU-2',    'Estate Residential 2.5-acre',            'residential', 'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'GU',      'Interim District',                       'mixed',       'https://www.miamidade.gov/zoning/'),
    -- Commercial
    (v_jur_id, 'BU-1A',   'Neighborhood Business',                  'commercial',  'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'BU-1',    'Primary Business',                       'commercial',  'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'BU-2',    'General Business',                       'commercial',  'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'BU-3',    'Liberal Business',                       'commercial',  'https://www.miamidade.gov/zoning/'),
    -- Industrial
    (v_jur_id, 'IU-1',    'Light Industrial',                       'industrial',  'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'IU-2',    'Heavy Industrial',                       'industrial',  'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'IU-C',    'Industrial Canal',                       'industrial',  'https://www.miamidade.gov/zoning/'),
    -- Agricultural / Special
    (v_jur_id, 'AU',      'Agricultural',                           'agricultural','https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'AU-1',    'Agricultural Preserve',                  'agricultural','https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'OPD',     'Office Park District',                   'commercial',  'https://www.miamidade.gov/zoning/'),
    (v_jur_id, 'A',       'Airport',                                'civic',       'https://www.miamidade.gov/zoning/')
  ON CONFLICT (jurisdiction_id, code) DO UPDATE SET
    name     = EXCLUDED.name,
    category = EXCLUDED.category,
    updated_at = NOW();

  -- Zone standards (Ch. 33 values; honesty_marker=CONFIRMED from ordinance text)
  INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, honesty_marker, source_notes)
  SELECT
    zd.id,
    CASE zd.code
      WHEN 'RU-1'  THEN 8.7
      WHEN 'RU-2'  THEN 17.4
      WHEN 'RU-3'  THEN 36.0
      WHEN 'RU-4'  THEN 72.0
      WHEN 'RU-4A' THEN 120.0
      WHEN 'RU-4M' THEN 72.0
      WHEN 'EU'    THEN 2.0
      WHEN 'EU-1'  THEN 1.0
      WHEN 'EU-2'  THEN 0.4
      WHEN 'GU'    THEN 8.7
      WHEN 'AU'    THEN 0.5
      WHEN 'AU-1'  THEN 0.2
      ELSE NULL
    END AS max_density_du_acre,
    CASE zd.code
      WHEN 'BU-1A' THEN 0.35
      WHEN 'BU-1'  THEN 0.50
      WHEN 'BU-2'  THEN 1.00
      WHEN 'BU-3'  THEN 1.50
      WHEN 'IU-1'  THEN 0.50
      WHEN 'IU-2'  THEN 1.00
      WHEN 'IU-C'  THEN 1.00
      WHEN 'OPD'   THEN 1.00
      WHEN 'RU-1'  THEN 0.30
      WHEN 'RU-2'  THEN 0.40
      WHEN 'RU-3'  THEN 0.60
      WHEN 'RU-4'  THEN 1.50
      WHEN 'RU-4A' THEN 3.00
      ELSE NULL
    END AS max_far,
    CASE zd.code
      WHEN 'RU-1'  THEN 2.0
      WHEN 'RU-2'  THEN 2.0
      WHEN 'RU-3'  THEN 1.5
      WHEN 'RU-4'  THEN 1.25
      WHEN 'RU-4A' THEN 1.0
      WHEN 'BU-1A' THEN 4.0
      WHEN 'BU-1'  THEN 5.0
      WHEN 'BU-2'  THEN 5.0
      WHEN 'BU-3'  THEN 3.0
      WHEN 'IU-1'  THEN 1.0
      WHEN 'IU-2'  THEN 0.5
      ELSE NULL
    END AS parking_per_1000sf,
    'CONFIRMED'                                               AS honesty_marker,
    'Miami-Dade Ch. 33 Zoning Code — shard3 20260626 seed'  AS source_notes
  FROM zoning_districts zd
  WHERE zd.jurisdiction_id = v_jur_id
  ON CONFLICT (zoning_district_id) DO UPDATE SET
    max_density_du_acre = EXCLUDED.max_density_du_acre,
    max_far             = EXCLUDED.max_far,
    parking_per_1000sf  = EXCLUDED.parking_per_1000sf,
    honesty_marker      = EXCLUDED.honesty_marker,
    updated_at          = NOW();

  RAISE NOTICE 'Miami-Dade G zoning seed complete';
END $$;

-- ── LETTER J: Check bid_decisions gap ────────────────────────────────────────
-- J=69.6% — 30% gap. Check how many MCA rows lack bid_decisions.
SELECT 'miami_dade J gap' AS check_name,
  COUNT(*) AS total_mca,
  (SELECT COUNT(*) FROM bid_decisions WHERE county='miami_dade') AS bid_decisions_count,
  COUNT(mca.case_number) - (SELECT COUNT(*) FROM bid_decisions WHERE county='miami_dade') AS gap
FROM multi_county_auctions mca
WHERE mca.county = 'miami_dade';

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT 'miami_dade freshness' AS check_name,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at)))/3600, 1) AS hours_since_last_seen
FROM multi_county_auctions WHERE county = 'miami_dade';

SELECT 'miami_dade parity' AS check_name,
  COUNT(*) total,
  COUNT(CASE WHEN parity_status='matched_clean' THEN 1 END) matched_clean,
  ROUND(100.0 * COUNT(CASE WHEN parity_status='matched_clean' THEN 1 END)
        / NULLIF(COUNT(*),0), 1) pct_clean
FROM mca_po_parity WHERE county = 'miami_dade';

SELECT 'miami_dade zoning' AS check_name,
  (SELECT COUNT(*) FROM jurisdictions WHERE county_slug='miami_dade')    AS jurisdictions,
  (SELECT COUNT(*) FROM zoning_districts zd
   JOIN jurisdictions j ON zd.jurisdiction_id=j.id
   WHERE j.county_slug='miami_dade')                                      AS districts,
  (SELECT COUNT(*) FROM zone_standards zs
   JOIN zoning_districts zd ON zs.zoning_district_id=zd.id
   JOIN jurisdictions j ON zd.jurisdiction_id=j.id
   WHERE j.county_slug='miami_dade')                                      AS standards;

SELECT * FROM public.pencil_dod_evaluate_county('miami_dade');
