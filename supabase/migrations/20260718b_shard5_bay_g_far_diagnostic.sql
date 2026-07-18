-- GOLD STANDARD shard-5 — bay county — G criterion FAR diagnostic
-- dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f
-- 2026-07-18
--
-- CONTEXT:
--   Bay G FAIL metric=92.3 [density=97.2 far=92.3 pk1000=]
--   FAR is the binding constraint (92.3% < 95% threshold).
--   density=97.2% is passing threshold but not counting since min() logic
--   with FAR at 92.3% drives the overall G metric.
--
--   Prior sessions (shard11, shard3 Jul 11) added zone_standards for
--   Bay County districts. Current FAR gap: ~7.7% of FAR-regulated parcels
--   have a matching zoning_districts row but NULL max_far in zone_standards,
--   OR their zone code has no zoning_districts row at all (orphan).
--
-- PURPOSE: Identify the FAR-gap districts so a future session (or the next
--   GHA wave) can supply ordinance-text values with honesty markers.
--   Per BLANK > WRONG: this migration contains NO fabricated FAR values.
--   It runs diagnostic SELECTs only — no DML.
--
-- HARD RULE: Do NOT write max_far values without citing the specific ordinance
--   section and source URL. Guessed FAR = ghost-success, BANNED.

SET statement_timeout = 0;

-- 1. How many FAR-applicable parcel_zones rows exist for bay?
SELECT 'bay_far_applicable_count' AS label,
  COUNT(pz.parcel_id) AS total_parcel_zones,
  COUNT(CASE WHEN zd.id IS NOT NULL THEN 1 END) AS matched_to_district,
  COUNT(CASE WHEN zd.id IS NOT NULL AND zs.max_far IS NOT NULL THEN 1 END) AS has_max_far,
  COUNT(CASE WHEN zd.id IS NOT NULL AND zd.far_regulated = true AND zs.max_far IS NULL THEN 1 END) AS far_regulated_null_far,
  ROUND(100.0 * COUNT(CASE WHEN zd.id IS NOT NULL AND zs.max_far IS NOT NULL THEN 1 END)
    / NULLIF(COUNT(CASE WHEN zd.id IS NOT NULL AND zd.far_regulated = true THEN 1 END), 0), 1) AS pct_far_covered
FROM parcel_zones pz
JOIN multi_county_auctions mca ON mca.parcel_id = pz.parcel_id AND lower(mca.county) = 'bay'
LEFT JOIN zoning_districts zd ON zd.id = (
  SELECT id FROM zoning_districts WHERE jurisdiction_id = pz.jurisdiction_id AND code = pz.zone_code LIMIT 1
)
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id;

-- 2. Which zone codes are used by bay parcels that have NULL max_far?
SELECT 'bay_far_gap_districts' AS label,
  pz.zone_code,
  pz.jurisdiction_id,
  j.name AS jurisdiction_name,
  zd.name AS district_name,
  zd.far_regulated,
  zs.max_far AS current_max_far,
  COUNT(DISTINCT mca.case_number) AS auction_count
FROM parcel_zones pz
JOIN multi_county_auctions mca ON mca.parcel_id = pz.parcel_id AND lower(mca.county) = 'bay'
LEFT JOIN jurisdictions j ON j.id = pz.jurisdiction_id
LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = pz.jurisdiction_id AND zd.code = pz.zone_code
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
WHERE zd.id IS NULL OR (zd.far_regulated = true AND zs.max_far IS NULL)
GROUP BY pz.zone_code, pz.jurisdiction_id, j.name, zd.name, zd.far_regulated, zs.max_far
ORDER BY auction_count DESC;

-- 3. Orphan parcel_zones for bay (zone_code with no matching zoning_districts row)
SELECT 'bay_orphan_zone_codes' AS label,
  pz.zone_code,
  pz.jurisdiction_id,
  j.name AS jurisdiction_name,
  COUNT(*) AS parcel_count
FROM parcel_zones pz
LEFT JOIN multi_county_auctions mca ON mca.parcel_id = pz.parcel_id AND lower(mca.county) = 'bay'
LEFT JOIN jurisdictions j ON j.id = pz.jurisdiction_id
LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = pz.jurisdiction_id AND zd.code = pz.zone_code
WHERE zd.id IS NULL
  AND mca.case_number IS NOT NULL
GROUP BY pz.zone_code, pz.jurisdiction_id, j.name
ORDER BY parcel_count DESC;

-- 4. Overall bay G evaluation
SELECT 'bay_g_eval_current' AS label;
SELECT * FROM public.pencil_dod_evaluate_county('bay');
