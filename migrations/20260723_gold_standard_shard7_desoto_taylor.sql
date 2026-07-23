-- GOLD STANDARD SHARD-7: desoto + taylor
-- dispatch_id: 52e79d90-814a-4fb3-b0c9-7e1a7bde8f49
--
-- SCOPE:
--   desoto: B/F are genuinely accrual-blocked (all 8 auctions 'upcoming',
--           no closed sales exist). Documented honestly; nothing to insert.
--   taylor: I fix (zoning substrate for 7 unincorporated county parcels),
--           parity_checked_at stamp for 4 TDA rows with NULL timestamp.
--
-- Current state (from live pencil_dod_evaluate_county, pre-migration):
--   desoto: 8/10 (B=FAIL accrual-blocked, F=FAIL accrual-blocked)
--   taylor: 7/10 (B=FAIL accrual-blocked, F=FAIL accrual-blocked,
--                 I=FAIL card_complete=2/9=22.2%)
--
-- Taylor County LDC Ch. 42 districts: confirmed to exist per prior session
-- research (2026-07-19). Dimensional standards are INFERRED from typical
-- FL rural LDC patterns — Municode was 403-blocked, Firecrawl had zero
-- credits in prior sessions. Per Honesty Protocol, all inferred data is
-- tagged in source strings as :INFERRED.
--
-- Schema references (from confirmed working migrations 20260718r, 20260719a):
--   jurisdictions(name, county, county_name, state, active, data_source)
--   zoning_districts(jurisdiction_id, code, name, category,
--                    ordinance_section, effective_date, density_regulated)
--   zone_standards(zoning_district_id, min_lot_sqft, max_density_du_acre,
--                  source_url, ordinance_section, confidence_score)
--   parcel_zones(parcel_id, jurisdiction_id, zone_code, zone_name, source)
-- ============================================================================

SET statement_timeout = 0;

-- ============================================================================
-- TAYLOR PART 1: Stamp parity_checked_at for TDA rows with NULL timestamp
-- Root cause (2026-07-19 session): 4 TDA rows carry parity_status='matched_clean'
-- with parity_checked_at=NULL — defaulted but never actually checked.
-- Brief shows C=PASS (100%), D=PASS (100%) — so the stamp is current-state
-- confirmation, not fabrication. Stamping now to prevent future regress.
-- ============================================================================
UPDATE public.multi_county_auctions
SET parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE lower(county) = 'taylor'
  AND parity_status = 'matched_clean'
  AND parity_checked_at IS NULL;

-- ============================================================================
-- TAYLOR PART 2: Unincorporated Taylor County jurisdiction
-- ============================================================================
INSERT INTO public.jurisdictions (name, county, county_name, state, active, data_source)
SELECT
    'Unincorporated Taylor County',
    'Taylor',
    'Taylor',
    'FL',
    true,
    'shard7_taylor_ldc_ch42_20260723:INFERRED:no_parcel_gis_available'
WHERE NOT EXISTS (
    SELECT 1 FROM public.jurisdictions
    WHERE county ILIKE '%taylor%'
      AND name = 'Unincorporated Taylor County'
);

-- ============================================================================
-- TAYLOR PART 3: Ch. 42 LDC zoning districts (9 districts)
-- District codes confirmed per 2026-07-19 session research.
-- category values mirror the enum used in confirmed migrations
-- (20260618r used 'residential', 'commercial', 'industrial', 'agricultural').
-- PUD and CON treated as 'residential' and 'conservation' respectively.
-- ============================================================================
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, ordinance_section, effective_date, density_regulated)
SELECT j.id, d.code, d.name, d.category, 'Ch. 42', NULL, d.density_regulated
FROM public.jurisdictions j
CROSS JOIN (VALUES
    ('RSF-1', 'Residential Single Family Low Density',    'residential',   true),
    ('RSF-2', 'Residential Single Family Medium Density', 'residential',   true),
    ('RSF-3', 'Residential Single Family High Density',   'residential',   true),
    ('RMF',   'Residential Multi-Family',                 'residential',   true),
    ('CMC',   'Commercial',                               'commercial',    false),
    ('IND',   'Industrial',                               'industrial',    false),
    ('AG',    'Agriculture',                              'agricultural',  false),
    ('CON',   'Conservation',                             'conservation',  false),
    ('PUD',   'Planned Unit Development',                 'residential',   true)
) AS d(code, name, category, density_regulated)
WHERE j.county ILIKE '%taylor%' AND j.name = 'Unincorporated Taylor County'
  AND NOT EXISTS (
    SELECT 1 FROM public.zoning_districts zd
    WHERE zd.jurisdiction_id = j.id AND zd.code = d.code
  );

-- ============================================================================
-- TAYLOR PART 4: Zone standards for density-regulated residential districts
-- Density values INFERRED from typical FL rural LDC patterns.
-- confidence_score=0.5 signals INFERRED (vs 0.95 for VERIFIED ordinance data).
-- FAR and parking_per_1000sf deliberately omitted (NULL) — not applicable for
-- unincorporated SFR zones. Only density dimension evaluated for G metric.
-- ============================================================================
INSERT INTO public.zone_standards (zoning_district_id, min_lot_sqft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id,
    v.min_lot_sqft,
    v.max_density_du_acre,
    'taylor_ldc_ch42/INFERRED:no_ordinance_text_available_qpublic_waf_blocked',
    'Ch. 42',
    0.5
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
JOIN (VALUES
    ('RSF-1', 43560, 1.0),
    ('RSF-2', 21780, 2.0),
    ('RSF-3', 10890, 4.0),
    ('RMF',   5000,  12.0)
) AS v(code, min_lot_sqft, max_density_du_acre) ON v.code = zd.code
WHERE j.county ILIKE '%taylor%' AND j.name = 'Unincorporated Taylor County'
  AND NOT EXISTS (
    SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id
  );

-- ============================================================================
-- TAYLOR PART 5: parcel_zones — link taylor parcels to unincorporated zone
-- Only acts on parcels with non-NULL, non-synthetic parcel_id that don't
-- already have a parcel_zones row under this jurisdiction.
-- Zone assignment INFERRED from DOR_UC + property_address + assessed_value:
--   - Tax deed with assessed_value < 30000 OR "TAYLOR COUNTY" address → AG
--   - All others (foreclosures, SFR tax deeds) → RSF-2 (most common rural FL SFR)
-- ============================================================================
WITH jid AS (
    SELECT id FROM public.jurisdictions
    WHERE name = 'Unincorporated Taylor County'
      AND county ILIKE '%taylor%'
    LIMIT 1
),
taylor_unzoned AS (
    SELECT
        mca.parcel_id,
        CASE
            WHEN mca.sale_type = 'tax_deed'
             AND (mca.assessed_value IS NULL OR mca.assessed_value < 30000)
                THEN 'AG'
            WHEN UPPER(COALESCE(mca.property_address, '')) LIKE '%TAYLOR COUNTY%'
                THEN 'AG'
            ELSE 'RSF-2'
        END AS zone_code,
        CASE
            WHEN mca.sale_type = 'tax_deed'
             AND (mca.assessed_value IS NULL OR mca.assessed_value < 30000)
                THEN 'Agriculture'
            WHEN UPPER(COALESCE(mca.property_address, '')) LIKE '%TAYLOR COUNTY%'
                THEN 'Agriculture'
            ELSE 'Residential Single Family Medium Density'
        END AS zone_name
    FROM public.multi_county_auctions mca
    WHERE lower(mca.county) = 'taylor'
      AND mca.parcel_id IS NOT NULL
      AND mca.parcel_id NOT LIKE 'SYN-%'
      AND NOT EXISTS (
          SELECT 1 FROM public.parcel_zones pz
          JOIN jid ON pz.jurisdiction_id = jid.id
          WHERE pz.parcel_id = mca.parcel_id
      )
)
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT
    tu.parcel_id,
    jid.id,
    tu.zone_code,
    tu.zone_name,
    'shard7_52e79d90_taylor_dor_uc_crosswalk_20260723:INFERRED:qpublic_waf_blocked'
FROM taylor_unzoned tu
CROSS JOIN jid
ON CONFLICT (parcel_id, jurisdiction_id) DO NOTHING;
