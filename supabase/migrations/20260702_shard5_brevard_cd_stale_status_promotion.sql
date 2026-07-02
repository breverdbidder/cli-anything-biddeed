-- SHARD-5: brevard C/D stale parity_status promotion (tier1-matched rows stuck as
-- tier1_only/mca_only despite sold_amount already equaling tier1_sold_amount)
-- dispatch_id: bec9a9b3-ce1c-4a46-b7e0-a861096f5ffb
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via ULTRALOOP audit workflow wf_63692fb6-dbb,
-- brevard C/D dimension): parity_source LIKE 'tier1%%' is already correctly set on these
-- rows (this is NOT the labeling-prefix bug fixed by 20260702_shard1_pencil_dod_cd_tier1_filter.sql),
-- but parity_status was never advanced past 'tier1_only'/'mca_only' even though
-- sold_amount = tier1_sold_amount exactly -- i.e. the matcher recorded the independent
-- tier1 outcome but a status-write step did not run/complete for these rows.
--
-- FIX: promote parity_status to 'matched_clean' wherever the amounts already agree exactly.
-- This does not fabricate any new match -- it corrects a stale status on rows that were
-- already, by their own stored sold_amount/tier1_sold_amount values, in agreement.
--
-- Dry-run verified immediately before apply: 111 rows matched (audit workflow found 114
-- ~40 min earlier; small drift consistent with tier1-promote-hourly cron continuing to run
-- concurrently -- expected, not a discrepancy).
--
-- VERIFIED live via pencil_dod_evaluate_county('brevard') before/after:
--   C: 83.9% (matched_clean=6033) -> 85.5% (matched_clean=6144)
--   D: 85.9% (matched_any=6172)   -> 87.4% (matched_any=6280)
--   A/B/E/F/G/H/I/J unaffected (confirmed no regression)
-- Still below the 95% threshold on both -- residual gap is a combination of ~781
-- sale_type-mislabeled phantom duplicate rows (flagged for pipeline-owner review, NOT
-- fixed here -- changing sale_type classification needs verification against criterion A)
-- and ~203 genuinely unharvested cases (redeemed/cancelled tax-deed rows structurally
-- cannot match; open foreclosure filings with no disposition yet need real harvesting).
--
-- Applied live 2026-07-02 via Supabase Management API; this file documents it.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean'
WHERE lower(county) = 'brevard'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
  AND sold_amount IS NOT NULL
  AND tier1_sold_amount IS NOT NULL
  AND sold_amount = tier1_sold_amount
  AND parity_status <> 'matched_clean'
  AND parity_source LIKE 'tier1%';
