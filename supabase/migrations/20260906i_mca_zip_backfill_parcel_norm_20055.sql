-- Issue #20055: multi_county_auctions.zip backfill from fl_parcels/zw_parcels via
-- NORMALIZED parcel_id join.
--
-- NORMALIZER REUSE: the issue asked to reuse the existing FF/winnerdata parcel-id
-- normalizer rather than invent a new one. The canonical normalizer lives in
-- scripts/property_appraiser/common.py:_norm_text() -- Python
-- `re.sub(r"[^A-Z0-9]", "", str(s).upper())`. Its exact SQL equivalent is
-- `upper(regexp_replace(parcel_id, '[^A-Za-z0-9]', '', 'g'))`, used below and in the
-- live backfill. fl_parcels already had a narrower expression index
-- (idx_fl_parcels_co_no_parcel_norm, strips only '-', ' ', '*') which under-matched
-- against dot/slash variants seen in the auction harvest -- this migration adds the
-- full-normalizer equivalent alongside it (does not replace/drop the existing one).
--
-- zw_parcels already carries a fully-populated `pin_clean` column (0 nulls across
-- 10,514,611 rows, confirmed live) using this exact same normalization, plus
-- idx_zw_parcels_pin_clean -- reused as-is for the fallback join, no new DDL needed
-- there.
--
-- PERFORMANCE NOTE (deviation from issue's suggested approach, logged per K3):
-- the issue asked for "a generated/stored parcel_id_norm column ... with a btree
-- index" built via a post-reboot pg_cron trick, because the box was assumed
-- reachable only in ~14-minute windows between whole-compute-instance reboots
-- (confirmed real and ongoing per docs/ops/LAUNCH_READINESS_T60_2026-09-05.md --
-- Supabase project mocerqjnksmhcjzxrewo restarts every 10-15 min, ~95-96
-- restarts/24h at time of writing). A stored generated column on an 11 GB /
-- 10,516,355-row table requires a full table rewrite (heavy, high risk of being
-- killed mid-rewrite by the next reboot with no partial progress kept). A plain
-- (non-generated) expression index achieves the same query-acceleration goal
-- without rewriting the table -- and was proven live: applied via the Supabase
-- Management API (api.supabase.com/v1/projects/.../database/query, using
-- SUPABASE_ACCESS_TOKEN -- direct psql/pooler auth failed in this runner, the
-- same known constraint as decision_log ids 169/205/287) with
-- `maintenance_work_mem='1GB'`, non-concurrent, single statement, and finished in
-- 45 seconds (well inside the reboot window; no pg_cron scheduling was needed).

CREATE INDEX IF NOT EXISTS idx_fl_parcels_co_no_parcel_norm_alnum
    ON public.fl_parcels USING btree (
        co_no,
        upper(regexp_replace(parcel_id, '[^A-Za-z0-9]'::text, ''::text, 'g'::text))
    );

-- RPC used by the harvest ingest path (scripts/realauction_winner_harvest.py) to
-- resolve a zip for a freshly-scraped row when the platform's own city/state string
-- doesn't carry one. SECURITY DEFINER + explicit grant, matching the pattern used by
-- public.ff_mls_parcel_audit (20260824_ff_verification_badge_rpc_v2_mls_parcel_audit.sql).
-- Collision-safe: returns a row only when every fl_parcels match for the normalized
-- parcel_id agrees on a single, well-formed 5-digit zip; ambiguous or garbage
-- (e.g. phy_zipcd='0', a real sentinel value confirmed live in fl_parcels) matches
-- return no row rather than guessing.
CREATE OR REPLACE FUNCTION public.mca_parcel_zip_lookup(p_co_no integer, p_parcel_id text)
RETURNS TABLE(zip text, phy_addr1 text, phy_city text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT z, addr1, city FROM (
    SELECT
      left(fp.phy_zipcd, 5) AS z,
      (array_agg(fp.phy_addr1 ORDER BY fp.parcel_id))[1] AS addr1,
      (array_agg(fp.phy_city ORDER BY fp.parcel_id))[1] AS city,
      count(*) OVER () AS distinct_zips
    FROM public.fl_parcels fp
    WHERE fp.co_no = p_co_no
      AND fp.phy_zipcd ~ '^[0-9]{5}'
      AND upper(regexp_replace(fp.parcel_id, '[^A-Za-z0-9]', '', 'g'))
          = upper(regexp_replace(p_parcel_id, '[^A-Za-z0-9]', '', 'g'))
    GROUP BY left(fp.phy_zipcd, 5)
  ) x
  WHERE distinct_zips = 1;
$$;

REVOKE ALL ON FUNCTION public.mca_parcel_zip_lookup(integer, text) FROM public;
GRANT EXECUTE ON FUNCTION public.mca_parcel_zip_lookup(integer, text) TO anon, authenticated, service_role;
