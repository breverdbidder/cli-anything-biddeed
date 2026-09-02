-- Issue #19720 Phase 4 item 13 -- harvest_golden_check(): diff golden set against
-- the live table's current sale_result. A full "re-harvest before diffing" variant
-- would need to invoke the credentialed realforeclose/realtaxdeed scripts per call
-- (spends a login every run) -- out of scope for this function; callers that want a
-- true re-harvest should run scripts/harvest_daily_sweep.py or
-- scripts/realtdm_completeness_sweep.py first, then call this to diff.
CREATE OR REPLACE FUNCTION public.harvest_golden_check()
RETURNS TABLE (
  county text, platform text, case_number text,
  expected_sale_result text, actual_sale_result text, pass boolean
)
LANGUAGE sql
STABLE
SECURITY INVOKER
AS $$
  -- case_number is not globally unique across sale_type within a county (confirmed live:
  -- brevard case_number '260053' exists as both an unrelated foreclosure row and the
  -- realtdm tax_deed row) -- platform pins sale_type so the join can't cross-match.
  SELECT g.county, g.platform, g.case_number, g.expected_sale_result,
         m.sale_result AS actual_sale_result,
         (m.sale_result IS NOT DISTINCT FROM g.expected_sale_result) AS pass
  FROM public.harvest_golden_set g
  LEFT JOIN public.multi_county_auctions m
    ON lower(m.county) = lower(g.county) AND m.case_number = g.case_number
    AND m.sale_type = (CASE WHEN g.platform = 'realforeclose' THEN 'foreclosure' ELSE 'tax_deed' END)
$$;

COMMENT ON FUNCTION public.harvest_golden_check() IS 'Issue #19720 Phase 4 -- diffs harvest_golden_set expected_sale_result against multi_county_auctions.sale_result for the same (county, case_number). Run scripts/harvest_daily_sweep.py or scripts/realtdm_completeness_sweep.py first for a true re-harvest-then-diff.';
