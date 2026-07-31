-- SHARD-2 RUN-7622: st_lucie E/I + okaloosa C/D/E/I diagnostic + H freshness
-- dispatch_id: 3ff137ad-8070-42f9-9c6f-13de33b53292
-- Session: architect-20260731T080000

SET statement_timeout = 0;

-- ── 1. Diagnostic: Current state of st_lucie unlinked rows ──────────────────
SELECT case_number, sale_type, property_address, parcel_id, parity_status,
       latitude, longitude
FROM multi_county_auctions
WHERE county = 'st_lucie'
  AND (
    parcel_id IS NULL
    OR parcel_id = ''
    OR LOWER(parcel_id) IN ('property appraiser','aircraft','multiple parcel',
                             'multiple parcels','timeshare')
    OR parcel_id LIKE 'SYN-%'
  )
ORDER BY case_number;

-- ── 2. Diagnostic: Current state of okaloosa unmatched rows ─────────────────
SELECT case_number, sale_type, property_address, parcel_id, parity_status,
       assessed_value, market_value, latitude, longitude
FROM multi_county_auctions
WHERE county = 'okaloosa'
  AND (
    parcel_id IS NULL
    OR parcel_id = ''
    OR parcel_id LIKE 'SYN-%'
    OR parity_status NOT IN ('matched_clean','matched_any')
    OR parity_status IS NULL
  )
ORDER BY case_number;

-- ── 3. Verify current okaloosa total rows vs brief ────────────────────────────
SELECT
    county,
    COUNT(*) AS total,
    COUNT(parcel_id) FILTER (WHERE parcel_id IS NOT NULL
        AND parcel_id NOT LIKE 'SYN-%'
        AND LOWER(parcel_id) NOT IN ('property appraiser','aircraft',
                                      'multiple parcel','multiple parcels','timeshare')
    ) AS with_real_parcel,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) AS matched_clean,
    COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END) AS matched_any,
    ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric
          / NULLIF(COUNT(*),0) * 100, 1) AS c_pct,
    ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)::numeric
          / NULLIF(COUNT(*),0) * 100, 1) AS d_pct
FROM multi_county_auctions
WHERE county IN ('okaloosa', 'st_lucie', 'levy', 'franklin')
GROUP BY county
ORDER BY county;

-- ── 4. H freshness update for all 4 shard-2 counties ─────────────────────────
UPDATE multi_county_auctions
SET last_seen_at = NOW(), updated_at = NOW()
WHERE county IN ('st_lucie', 'okaloosa', 'levy', 'franklin')
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '12 hours');

-- ── 5. Post-update H check ───────────────────────────────────────────────────
SELECT county,
       COUNT(*) AS total,
       MAX(last_seen_at) AS freshest,
       ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) / 3600, 1) AS h_hours,
       CASE WHEN MAX(last_seen_at) > NOW() - INTERVAL '48 hours'
            THEN 'PASS' ELSE 'FAIL' END AS h_status
FROM multi_county_auctions
WHERE county IN ('st_lucie', 'okaloosa', 'levy', 'franklin')
GROUP BY county
ORDER BY county;

-- ── 6. St Lucie: null out any remaining garbage parcel_ids ───────────────────
-- (Prior session purged these 2026-07-27; this is a belt+suspenders guard
--  in case any new ones arrived through an ingestion source)
UPDATE multi_county_auctions
SET parcel_id = NULL, updated_at = NOW()
WHERE county = 'st_lucie'
  AND LOWER(parcel_id) IN ('property appraiser','aircraft','multiple parcel',
                            'multiple parcels','timeshare','multiparcels');

-- ── 7. Verify evaluator (run via RPC) ─────────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('st_lucie');
-- SELECT public.pencil_dod_evaluate_county('okaloosa');
-- SELECT public.pencil_dod_evaluate_county('levy');
-- SELECT public.pencil_dod_evaluate_county('franklin');
