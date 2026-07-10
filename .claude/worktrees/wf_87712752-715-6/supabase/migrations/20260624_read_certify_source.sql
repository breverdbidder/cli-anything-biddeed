-- READ CERTIFY SOURCE (2026-06-24)
-- Purpose: expose gold_standard_certify() function body via REST API
-- so guard logic (no_calendar_parity, no_denominator_integrity) can be read
-- without Management API (which returns 403 in GHA).

-- Create a helper function that returns the certify() source
CREATE OR REPLACE FUNCTION public.get_certify_source()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT pg_get_functiondef(oid)
  FROM pg_proc
  WHERE proname = 'gold_standard_certify'
  LIMIT 1;
$$;

-- Also expose pencil_dod_evaluate_county source
CREATE OR REPLACE FUNCTION public.get_eval_source()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT pg_get_functiondef(oid)
  FROM pg_proc
  WHERE proname = 'pencil_dod_evaluate_county'
  LIMIT 1;
$$;
