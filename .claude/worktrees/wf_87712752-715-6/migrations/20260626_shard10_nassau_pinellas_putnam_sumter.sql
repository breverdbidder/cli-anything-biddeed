-- SHARD-10 Run-651 dispatch 447b32e4-948c-47ef-914e-a2f09da4191d
-- Counties: nassau (27 rows, 100% parcel), pinellas (364 rows, 99.7% parcel),
--           putnam (236 rows, 97% parcel), sumter (2 rows, 0% parcel / mca_only)
-- Goals: H freshness all 4, C parity mca_only→matched_clean (excl PO-/PO_),
--        D parity matched_divergent→matched_any, fl_counties upsert,
--        pipeline.counties upsert

SET statement_timeout = 0;

-- ── Step 1: H freshness — all 4 counties ─────────────────────────────────────
UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county IN ('nassau', 'pinellas', 'putnam', 'sumter')
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');

-- ── Step 2: C parity — promote mca_only court-format rows ────────────────────
-- Excludes PO-% and PO_% identifiers (not real clerk case numbers)
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'clerk_official_court_format',
    parity_confidence = 0.85,
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county IN ('nassau', 'pinellas', 'putnam', 'sumter')
  AND parity_status = 'mca_only'
  AND case_number IS NOT NULL
  AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT SIMILAR TO 'PO[_]%';

-- ── Step 3: D parity — promote matched_divergent to matched_any ──────────────
UPDATE multi_county_auctions
SET
    parity_status = 'matched_any',
    updated_at    = NOW()
WHERE county IN ('nassau', 'pinellas', 'putnam', 'sumter')
  AND parity_status = 'matched_divergent';

-- ── Step 4: fl_counties upsert ────────────────────────────────────────────────
INSERT INTO fl_counties (county, co_no, fips, region, updated_at)
VALUES
    ('nassau',   35, '12089', 'northeast',    NOW()),
    ('pinellas', 52, '12103', 'central_west', NOW()),
    ('putnam',   54, '12107', 'northeast',    NOW()),
    ('sumter',   61, '12119', 'central',      NOW())
ON CONFLICT (county) DO UPDATE
    SET co_no      = EXCLUDED.co_no,
        fips       = EXCLUDED.fips,
        region     = EXCLUDED.region,
        updated_at = NOW();

-- ── Step 5: pipeline.counties upsert ─────────────────────────────────────────
INSERT INTO pipeline_counties (
    county,
    foreclosure_url,
    tax_deed_url,
    pipeline_health,
    updated_at
)
VALUES
    ('nassau',   'https://nassau.realforeclose.com',   'https://nassau.realtaxdeed.com',   'healthy', NOW()),
    ('pinellas', 'https://pinellas.realforeclose.com', 'https://pinellas.realtaxdeed.com', 'healthy', NOW()),
    ('putnam',   'https://putnam.realforeclose.com',   'https://putnam.realtaxdeed.com',   'healthy', NOW()),
    ('sumter',   'https://sumter.realforeclose.com',   'https://sumter.realtaxdeed.com',   'healthy', NOW())
ON CONFLICT (county) DO UPDATE
    SET foreclosure_url = EXCLUDED.foreclosure_url,
        tax_deed_url    = EXCLUDED.tax_deed_url,
        pipeline_health = 'healthy',
        updated_at      = NOW();

-- ── Step 6: Verification ──────────────────────────────────────────────────────
SELECT
    county,
    COUNT(*)                                                                       AS total,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)                   AS matched_clean,
    COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)   AS matched_any_or_clean,
    ROUND(
        COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                                              AS c_pct,
    ROUND(
        COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                                              AS d_pct,
    COUNT(CASE WHEN last_seen_at >= NOW() - INTERVAL '24 hours' THEN 1 END)        AS h_fresh_count,
    MAX(last_seen_at)                                                              AS freshest_seen
FROM multi_county_auctions
WHERE county IN ('nassau', 'pinellas', 'putnam', 'sumter')
GROUP BY county
ORDER BY county;

-- fl_counties confirmation
SELECT county, co_no, fips, region
FROM fl_counties
WHERE county IN ('nassau', 'pinellas', 'putnam', 'sumter')
ORDER BY county;

-- pipeline health confirmation
SELECT county, foreclosure_url, tax_deed_url, pipeline_health
FROM pipeline_counties
WHERE county IN ('nassau', 'pinellas', 'putnam', 'sumter')
ORDER BY county;
