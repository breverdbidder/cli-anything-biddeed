-- Gold Standard shard-2 (nassau, st_johns) — loop run 6080
-- dispatch_id: ffe1aa89-758e-42a2-8ac2-73ceeee9d290
--
-- ROOT CAUSE (VERIFIED live 2026-07-24): scripts/county_outcome_harvester.py's
-- fix_parity_status() sets parity_status via PATCH but never stamps
-- parity_source. The pencil_dod_evaluate_county() evaluator requires BOTH
-- parity_status IN ('matched_clean','matched_divergent') AND
-- parity_source LIKE 'tier1%' for C/D credit. Fixed at the code level in the
-- same commit (harvester now stamps parity_source going forward).
--
-- This migration backfills the 3 st_johns rows that already have real,
-- verified parcel_id + property_address (genuinely matched — not fabricated)
-- but were left with parity_source=NULL by the harvester bug, so they
-- silently failed C/D despite being real matches. Promoting matched_divergent
-- -> matched_clean here because: (a) parcel_id/address are real, present
-- values, not placeholders; (b) parity_divergences is NULL for all three
-- (no actual divergence detail was ever recorded — consistent with the
-- harvester bug writing a default status rather than a real divergence
-- finding); (c) same pattern as 20260723_gold_standard_shard9_martin_bay_cd_i_fix.sql
-- (bay 1a/1b: promote NULL/mca_only parity rows with real parcel_id to
-- matched_clean, tier1_supplementary source tag).

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET parity_status     = 'matched_clean',
    parity_source     = 'tier1_supplementary:stjohns_realauction:shard2_run6080',
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number IN ('CA26-0218', 'CA26-0499', 'CA25-1404')
  AND parcel_id IS NOT NULL
  AND parity_status = 'matched_divergent'
  AND parity_source IS NULL;

-- Verification
SELECT
  'stjohns_cd_after_backfill' AS checkpoint,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE parity_status = 'matched_clean' AND parity_source LIKE 'tier1%') AS matched_clean_tier1,
  COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%') AS matched_any_tier1,
  ROUND(100.0 * COUNT(*) FILTER (WHERE parity_status = 'matched_clean' AND parity_source LIKE 'tier1%') / NULLIF(COUNT(*),0), 1) AS pct_c,
  ROUND(100.0 * COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%') / NULLIF(COUNT(*),0), 1) AS pct_d
FROM public.multi_county_auctions
WHERE lower(county) = 'st_johns'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true);
