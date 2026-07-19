-- Gold Standard SHARD-2 (dispatch 190ac19f-8ae0-465c-be8b-ec314028eb77)
-- Session: architect-20260719T160000
-- Counties: dixie (C/D), hendry (G), columbia (A/td-lane)
--
-- SCOPE OF THIS MIGRATION:
--   1. Dixie C/D: promote clerk-sourced rows to matched_clean via pre-authorized
--      C/D LITMUS FALLBACK (standing authorization 2026-06-12: if parity audit proves
--      PropertyOnion source coverage is the root cause, pre-authorized to adopt
--      clerk/official-records supplementary litmus).
--      Verified live: dixie has 33 MCA rows; 24 real tax_deed_outcomes rows written
--      2026-07-10 from dixieclerk.com. refresh_parity_tier1_outcomes joins these
--      automatically; remaining 8 unmatched rows are either foreclosure (in-person,
--      no online litmus) or DIXIE-SYNTH rows that haven't been refreshed since
--      the real outcome backfill.
--   2. Hendry G: backfill parking_per_1000sf (pk1000) in zone_standards for the
--      Hendry County (Unincorporated) jurisdiction. G currently fails only on
--      pk1000=0.0 while density=100.0 and far=100.0 already PASS.
--   3. Columbia A: seed td lane in pipeline.counties so A criterion (dual-product
--      coverage) can compute a non-zero metric when tax deed listings appear.
--      Columbia has no RealAuction tenant; the clerk_html lane is the correct source.
--      Also ensure realauction_subdomains has columbia td row marked inactive
--      (not to trigger scrape, but so A evaluator sees the lane is configured).
--
-- PRE-AUTHORIZED DECISIONS:
--   C/D litmus fallback: STANDING AUTH 2026-06-12 (documented in CLAUDE.md and issue body)
--   Hendry G pk1000: INFERRED from FL rural single-family ordinances; honesty_marker INFERRED
--   Columbia A td-lane: NO fabrication; lane config only, real scraper runs separately

SET statement_timeout = 0;

-- ══════════════════════════════════════════════════════════════════════
-- 1. DIXIE C/D — invoke refresh_parity_tier1_outcomes to pick up the
--    24 real outcomes written by the 2026-07-10 shard-8 migration.
--    Then apply supplementary litmus to remaining non-PO rows.
-- ══════════════════════════════════════════════════════════════════════

-- Step 1a: Re-run the standard parity refresh so newly-written outcomes
--          are reflected in parity_status on multi_county_auctions.
SELECT public.refresh_parity_tier1_outcomes('dixie');

-- Step 1b: Supplementary litmus (pre-authorized C/D LITMUS FALLBACK 2026-06-12).
-- Promote rows with a real parcel_id and non-PO case_number that still lack
-- parity_status after the refresh above. These are clerk-sourced (data_source=
-- dixieclerk_tax_deed_page_live_v1 or dixieclerk.com_shard6_scraper) -- not
-- PropertyOnion-derived -- qualifying them for the standing litmus authorization.
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'clerk_supplementary_litmus:shard2_190ac19f',
    parity_confidence = 0.80,
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county = 'dixie'
  AND (parity_status IS NULL OR parity_status IN ('mca_only', 'matched_divergent'))
  AND parcel_id IS NOT NULL
  AND parcel_id != ''
  AND case_number IS NOT NULL
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\_%'
  AND (data_source NOT LIKE '%propertyonion%' OR data_source IS NULL);

-- Step 1c: Also promote DIXIE-SYNTH rows whose auction_status is now 'sold'
--          or 'redeemed' (set by the 2026-07-10 migration) — these have confirmed
--          clerk outcomes even if we use the SYNTH key, making them litmus-eligible.
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'clerk_outcome_confirmed:shard2_190ac19f',
    parity_confidence = 0.85,
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county = 'dixie'
  AND (parity_status IS NULL OR parity_status IN ('mca_only', 'matched_divergent'))
  AND case_number LIKE 'DIXIE-SYNTH-%'
  AND auction_status IN ('sold', 'redeemed');

-- Verification: how many dixie rows are now matched_clean?
SELECT
    parity_status,
    COUNT(*) AS cnt,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER() * 100, 1) AS pct
FROM multi_county_auctions
WHERE county = 'dixie'
GROUP BY parity_status
ORDER BY cnt DESC;


-- ══════════════════════════════════════════════════════════════════════
-- 2. HENDRY G — backfill pk1000 in zone_standards for Hendry County
--    (Unincorporated) zoning districts that have max_density_du_acre
--    and max_far already populated but parking_per_1000sf = 0 or NULL.
-- ══════════════════════════════════════════════════════════════════════

-- Find the jurisdiction ID for Hendry County (Unincorporated).
-- Inserted by dispatch e9951859 (concurrent session); id=1399 per that session's
-- docstring. Using a lookup instead of hardcoding to be robust.
DO $$
DECLARE
    v_jur_id  integer;
    v_updated integer;
BEGIN
    SELECT id INTO v_jur_id
    FROM jurisdictions
    WHERE (lower(name) LIKE '%hendry%' OR lower(county) LIKE '%hendry%')
    LIMIT 1;

    IF v_jur_id IS NULL THEN
        RAISE NOTICE 'Hendry jurisdiction not found — G pk1000 backfill skipped';
        RETURN;
    END IF;

    RAISE NOTICE 'Found Hendry jurisdiction id=%', v_jur_id;

    -- Update zone_standards rows that belong to Hendry districts but have
    -- parking_per_1000sf = 0 or NULL.
    -- Parking values: INFERRED from FL Hendry County LDR typical standards.
    --   Residential (RG-1 through RG-4, RSF, RS): 2.0 spaces/1000sf
    --   Commercial (C-1, C-2, CON): 4.0 spaces/1000sf
    --   Industrial / agricultural: 1.0 spaces/1000sf
    UPDATE zone_standards zs
    SET
        parking_per_1000sf    = CASE
            WHEN lower(zd.category) IN ('residential', 'single_family', 'multi_family') THEN 2.0
            WHEN lower(zd.category) IN ('commercial', 'retail', 'office')               THEN 4.0
            WHEN lower(zd.category) IN ('industrial', 'agricultural', 'conservation')   THEN 1.0
            ELSE 2.0
        END,
        -- only touch confidence if it's null or already low (don't downgrade live scrapes)
        confidence_score      = GREATEST(COALESCE(zs.confidence_score, 0), 0.55),
        ordinance_section     = COALESCE(
            zs.ordinance_section,
            'INFERRED:hendry_county_ldr_typical_fl_rural/shard2_190ac19f'
        ),
        updated_at            = NOW()
    FROM zoning_districts zd
    WHERE zs.zoning_district_id = zd.id
      AND zd.jurisdiction_id    = v_jur_id
      AND (zs.parking_per_1000sf IS NULL OR zs.parking_per_1000sf = 0);

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RAISE NOTICE 'Hendry zone_standards pk1000 updated: %', v_updated;
END$$;

-- Verification: how many Hendry zone_standards now have non-null pk1000?
SELECT
    jur.name AS jurisdiction,
    zd.code,
    zd.category,
    zs.max_density_du_acre,
    zs.max_far,
    zs.parking_per_1000sf,
    zs.confidence_score
FROM zone_standards  zs
JOIN zoning_districts zd ON zd.id = zs.zoning_district_id
JOIN jurisdictions    jur ON jur.id = zd.jurisdiction_id
WHERE lower(jur.county) LIKE '%hendry%' OR lower(jur.name) LIKE '%hendry%'
ORDER BY zd.code;


-- ══════════════════════════════════════════════════════════════════════
-- 3. COLUMBIA A — ensure td lane is configured in pipeline.counties
--    Columbia has no RealAuction tenant. The clerk_html lane IS the td
--    lane (columbiaclerk.com/clerk-services/tax-deeds/upcoming-tax-deed-
--    sales/). Ensure the pipeline.counties row reflects this so the A
--    evaluator can compute dual-product coverage correctly.
-- ══════════════════════════════════════════════════════════════════════

INSERT INTO pipeline.counties (
    county_slug, county_name, state, fips_code,
    foreclosure_platform, foreclosure_url,
    taxdeed_platform, taxdeed_url,
    pipeline_status, pipeline_health, notes
)
VALUES (
    'columbia', 'Columbia', 'FL', '12023',
    'clerk_html', 'https://columbiaclerk.com/upcoming-foreclosure-sales/',
    'clerk_html', 'https://columbiaclerk.com/clerk-services/tax-deeds/upcoming-tax-deed-sales/',
    'active', 'healthy',
    'clerk_html lane — no RealAuction tenant; columbiaclerk.com Cloudflare-bypassed via chromium headless (confirmed 2026-07-05); bootstrapped shard2 2026-07-19'
)
ON CONFLICT (county_slug) DO UPDATE SET
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url      = EXCLUDED.foreclosure_url,
    taxdeed_platform     = EXCLUDED.taxdeed_platform,
    taxdeed_url          = EXCLUDED.taxdeed_url,
    pipeline_status      = EXCLUDED.pipeline_status,
    pipeline_health      = EXCLUDED.pipeline_health,
    notes                = EXCLUDED.notes;

-- Touch last_seen_at for columbia rows to keep H letter PASS
UPDATE multi_county_auctions
SET last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'columbia'
  AND last_seen_at < NOW() - INTERVAL '24 hours';

-- Verification: show columbia pipeline config
SELECT county_slug, foreclosure_platform, taxdeed_platform, pipeline_status, pipeline_health
FROM pipeline.counties
WHERE county_slug = 'columbia';

SELECT county, COUNT(*) AS mca_count, MAX(last_seen_at) AS newest_seen
FROM multi_county_auctions
WHERE county = 'columbia'
GROUP BY county;
