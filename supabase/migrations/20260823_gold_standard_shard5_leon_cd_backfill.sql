-- GOLD STANDARD shard-5 leon (dispatch 79ee1554): C/D parity backfill.
-- 47 parity_status IS NULL rows (6 upcoming foreclosure 08/25-09/02/2026,
-- 41 upcoming tax_deed 09/16/2026). Same independent-corroboration method as
-- the accepted clay precedent: paginated AJAX AITEM harvest of
-- leon.realforeclose.com + leon.realtaxdeed.com, cross-check by normalized
-- case_number, mark matched_clean parity_source='tier1_realforeclose_leon'.
--
-- Step 1 (executed live, not re-runnable from this file alone):
--   python3 scripts/realforeclose_aids_paginated_harvest.py leon realforeclose.com leon \
--     08/25/2026 08/28/2026 09/02/2026   (parsed=7 inserted_or_merged=7)
--   python3 scripts/realforeclose_aids_paginated_harvest.py leon realtaxdeed.com leon \
--     09/16/2026                          (parsed=34 inserted_or_merged=34, re-run twice,
--                                           deterministic 34/41 -- the AJAX preview endpoint
--                                           genuinely does not return case numbers 26-0089,
--                                           26-0090, 26-0093, 26-0096, 26-0097, 26-0098,
--                                           26-0099, 26-0102, 26-0103, 26-0106 for this date;
--                                           left unmatched rather than force-marked clean --
--                                           residual, not a fabricated pass)
--
-- Result (VERIFIED live via pencil_dod_evaluate_county): C 81.0%->96.0%,
-- D 81.0%->96.0%, both PASS (10 of the original 47 remain genuinely
-- unmatched -- see residual note above). leon now 9/10 (only I remains).

SET statement_timeout = 0;

UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_leon',
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'leon'
  AND lower(mca.county) = 'leon'
  AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
  AND normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
  AND normalize_case_number(mca.case_number) <> ''
  AND (mca.parity_status IS NULL OR mca.parity_status NOT IN ('matched_clean','matched_divergent'));
