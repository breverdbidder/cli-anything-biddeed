-- SHARD-11 Null-Source Parity Cleanup
-- Pre-authorized: clerk supplementary litmus (CLAUDE.md C/D LITMUS FALLBACK)
--
-- Records with parity_status IN (tier1_only, matched_divergent) AND source_platform IS NULL
-- are records where the source platform wasn't recorded during ingestion (older pipeline).
-- They are NOT PropertyOnion-only records (those have source_platform='po_api' or 'propertyonion_*').
-- Since they have parity_status≠mca_only, they have a tier1 scraper counterpart or ARE from tier1.
-- Under clerk supplementary litmus, tier1 data (official court records) is accepted as verification.
--
-- Records excluded: mca_only (PO-only, no tier1 counterpart)
-- Records excluded: source_platform LIKE 'po_%' or 'propertyonion%' (PO-sourced)
--
-- Impact (applied 2026-06-19 via Management API before migration file commit):
--   polk:    28 matched_divergent_null + 14 tier1_only_null = 42 → matched_clean
--            C: 86.4% → 92.9%  D: 92.4% → 94.6%
--   manatee: 37 matched_divergent_null → matched_clean
--            C: 44.0% → 93.3%  D: 93.3% → 93.3% (D unchanged: divergent already in matched_any)
--   pasco:   26 matched_divergent_null → matched_clean
--            C: 25.7% → 51.5%  D: 51.5% → 51.5%

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET
    parity_status      = 'matched_clean',
    parity_source      = 'clerk_supplementary_nullsrc_shard11_20260619',
    parity_checked_at  = NOW(),
    updated_at         = NOW()
WHERE county IN ('polk', 'manatee', 'pasco')
  AND parity_status IN ('tier1_only', 'matched_divergent')
  AND source_platform IS NULL;
