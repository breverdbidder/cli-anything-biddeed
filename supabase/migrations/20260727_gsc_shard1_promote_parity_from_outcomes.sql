-- GOLD STANDARD shard-1 (duval/union), dispatch 3aafe92d, 2026-07-27
-- Root cause (VERIFIED live): duval C/D fail because parity_status/parity_source
-- are never set for rows that already have a verified outcome in
-- foreclosure_outcomes/tax_deed_outcomes (the same trusted source
-- promote_tier1_from_outcomes() already uses for F). 41 of duval's 47
-- C-unmatched rows have a tax_deed_outcomes match purely by case_number+sale_type;
-- promote_tier1_from_outcomes() only ever touched tier1_sold_amount, never
-- parity_status/parity_source, so C/D stayed frozen while tier1_sold_amount moved.
--
-- This is county-agnostic (mirrors promote_tier1_from_outcomes exactly) so it
-- benefits every county with the same gap, not just duval.

SET statement_timeout = 0;

CREATE OR REPLACE FUNCTION public.promote_parity_from_outcomes()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_catalog'
AS $$
DECLARE v_n int;
BEGIN
  WITH src AS (
    SELECT lower(county) AS county, case_number, 'foreclosure' AS st
    FROM foreclosure_outcomes
    WHERE winning_bid IS NOT NULL AND COALESCE(data_source,'') NOT ILIKE '%promote%'
    UNION ALL
    SELECT lower(county), case_number, 'tax_deed'
    FROM tax_deed_outcomes
    WHERE winning_bid IS NOT NULL AND COALESCE(data_source,'') NOT ILIKE '%promote%'
  )
  UPDATE multi_county_auctions m
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_promoted_outcome_v1',
      updated_at    = now()
  FROM src s
  WHERE lower(m.county) = s.county
    AND m.case_number    = s.case_number
    AND m.sale_type       = s.st
    AND (m.parity_status IS DISTINCT FROM 'matched_clean'
         OR m.parity_source IS NULL
         OR m.parity_source NOT LIKE 'tier1%');
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN jsonb_build_object('promoted', v_n, 'at', now());
END $$;

GRANT EXECUTE ON FUNCTION public.promote_parity_from_outcomes() TO service_role;
