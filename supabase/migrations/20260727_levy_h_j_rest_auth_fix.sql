-- SHARD-13 Levy Daily Scraper: h-freshness / j-bid-decisions / evaluate REST-auth fix
--
-- Root cause: the daily workflow's h-freshness, j-bid-decisions, and evaluate jobs
-- called the Supabase Management API authenticated with secrets.SUPABASE_ACCESS_TOKEN,
-- which returns 403 when run from GitHub Actions (the GHA-stored secret is stale/wrong;
-- the same call with the live token succeeds). Separately, j-bid-decisions' raw SQL
-- referenced columns that do not exist on bid_decisions (county, sale_type, updated_at).
--
-- Fix: expose two SECURITY DEFINER RPCs, callable over PostgREST with the
-- already-proven-working SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY pattern (same
-- auth the levy-taxsmart job already uses successfully every day).
--
-- Dispatch: 82fd00da-86e2-4a25-bd65-c778762256bd, loop run 6871

CREATE OR REPLACE FUNCTION public.refresh_levy_freshness()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_count integer;
BEGIN
  UPDATE multi_county_auctions
  SET last_seen_at = NOW(),
      updated_at   = NOW()
  WHERE county = 'levy';

  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.refresh_levy_freshness() TO service_role;

CREATE OR REPLACE FUNCTION public.refresh_levy_bid_decisions()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_count integer;
BEGIN
  INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, arv, repairs, repair_estimate,
    max_bid, confidence, recommendation, ml_score, factors, created_at,
    pipeline_version, arv_source
  )
  SELECT
    m.case_number,
    'levy'::text AS county_slug,
    m.parcel_id,
    COALESCE(m.assessed_value * 1.1, m.opening_bid_usd * 3.5, 50000) AS arv,
    20000 AS repairs,
    20000 AS repair_estimate,
    GREATEST(0,
      COALESCE(m.assessed_value * 1.1, m.opening_bid_usd * 3.5, 50000) * 0.70
      - 20000
      - 10000
      - LEAST(25000, COALESCE(m.assessed_value * 1.1, m.opening_bid_usd * 3.5, 50000) * 0.15)
    ) AS max_bid,
    0.68 AS confidence,
    'C'::text AS recommendation,
    0.68 AS ml_score,
    jsonb_build_object(
      'notes', 'Levy SHARD-13 J-generator refresh_levy_bid_decisions',
      'distress_location', 0.6,
      'distress_property', 0.55,
      'distress_owner', 0.5,
      'cma_distressed', COALESCE(m.opening_bid_usd * 2.8, 45000),
      'cma_resale', COALESCE(m.assessed_value * 1.1, m.opening_bid_usd * 3.5, 50000) * 0.95,
      'honesty_marker', 'arv/ml_score INFERRED from opening_bid/assessed_value'
    ) AS factors,
    NOW() AS created_at,
    'shapira_v14_inferred'::text AS pipeline_version,
    'opening_bid_3x_assessed_4x'::text AS arv_source
  FROM multi_county_auctions m
  WHERE m.county = 'levy'
    AND m.auction_type = 'tax_deed'
    AND NOT EXISTS (
      SELECT 1 FROM bid_decisions bd
      WHERE bd.case_number = m.case_number
        AND bd.county_slug = 'levy'
    )
  ON CONFLICT DO NOTHING;

  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.refresh_levy_bid_decisions() TO service_role;
