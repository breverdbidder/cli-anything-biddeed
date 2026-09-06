-- Issue #20043 item 7 — Plaintiff Discount Index materialized view.
--
-- Thesis (Ariel): lenders/servicers write off non-performing assets on
-- their own fiscal calendars and let properties go to third parties at
-- deeper discounts in those windows. This is a scoreboard, not a model —
-- decision-support copy only, never "this bank will discount".
--
-- Depends on public.normalize_plaintiff() / plaintiff_norm from
-- 20260906a_plaintiff_norm_20043.sql. Coverage note (live counts at dispatch
-- time, see docs/spec/20043.md): sold_amount populated on 2,847/43,289
-- (6.6%) of 2024-01-01+ rows, plaintiff on 2,734 (6.3%), all three of
-- sold+plaintiff+market_value on only 142 — this view will be sparse until
-- issue #20043 item 2's harvest backfill lands (held this dispatch per the
-- restart-count precondition). A sparse view is still correct; the report
-- band renders "Pending — fewer than 3 observed third-party sales" for any
-- plaintiff below n=3, per the issue's own DoD.

CREATE MATERIALIZED VIEW IF NOT EXISTS public.plaintiff_discount_index AS
WITH base AS (
  SELECT
    mca.id,
    mca.plaintiff_norm,
    mca.sold_amount,
    mca.judgment_amount,
    mca.market_value,
    mca.auction_date,
    date_trunc('quarter', mca.auction_date)::date AS quarter,
    (mca.winning_bidder IS NOT NULL AND mca.winning_bidder NOT ILIKE '%plaintiff%') AS is_third_party,
    CASE WHEN mca.judgment_amount > 10000 AND mca.sold_amount > 1000
         THEN mca.sold_amount::numeric / mca.judgment_amount END AS sold_to_judgment,
    CASE WHEN mca.market_value > 10000 AND mca.sold_amount > 1000
         THEN mca.sold_amount::numeric / mca.market_value END AS sold_to_market
  FROM public.multi_county_auctions mca
  WHERE mca.plaintiff_norm IS NOT NULL
    AND mca.auction_date >= '2024-01-01'
    AND mca.sold_amount > 1000
),
all_time AS (
  SELECT
    plaintiff_norm,
    NULL::date AS quarter,
    count(*) FILTER (WHERE is_third_party)                                   AS n_third_party_sales,
    count(*)                                                                  AS n_total_sales,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY sold_to_judgment) FILTER (WHERE is_third_party) AS median_sold_to_judgment,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY sold_to_judgment) FILTER (WHERE is_third_party) AS p25_sold_to_judgment,
    min(sold_to_judgment)                                        FILTER (WHERE is_third_party)   AS min_sold_to_judgment,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY sold_to_market)  FILTER (WHERE is_third_party)   AS median_sold_to_market,
    (count(*) FILTER (WHERE is_third_party))::numeric / NULLIF(count(*), 0)   AS third_party_share
  FROM base
  GROUP BY plaintiff_norm
),
by_quarter AS (
  SELECT
    plaintiff_norm,
    quarter,
    count(*) FILTER (WHERE is_third_party)                                   AS n_third_party_sales,
    count(*)                                                                  AS n_total_sales,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY sold_to_judgment) FILTER (WHERE is_third_party) AS median_sold_to_judgment,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY sold_to_judgment) FILTER (WHERE is_third_party) AS p25_sold_to_judgment,
    min(sold_to_judgment)                                        FILTER (WHERE is_third_party)   AS min_sold_to_judgment,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY sold_to_market)  FILTER (WHERE is_third_party)   AS median_sold_to_market,
    (count(*) FILTER (WHERE is_third_party))::numeric / NULLIF(count(*), 0)   AS third_party_share
  FROM base
  GROUP BY plaintiff_norm, quarter
)
SELECT 'all_time'::text AS period_type, * FROM all_time
UNION ALL
SELECT 'quarter'::text AS period_type, * FROM by_quarter;

CREATE UNIQUE INDEX IF NOT EXISTS idx_plaintiff_discount_index_key
  ON public.plaintiff_discount_index (period_type, plaintiff_norm, COALESCE(quarter, '0001-01-01'::date));

-- Rank among plaintiffs with n>=3 (all-time), for the report band's
-- "plaintiff's rank among plaintiffs with n>=3" requirement.
CREATE OR REPLACE VIEW public.v_plaintiff_discount_rank AS
SELECT
  plaintiff_norm,
  n_third_party_sales,
  median_sold_to_judgment,
  min_sold_to_judgment,
  third_party_share,
  rank() OVER (ORDER BY median_sold_to_judgment ASC) AS rank_by_discount
FROM public.plaintiff_discount_index
WHERE period_type = 'all_time'
  AND n_third_party_sales >= 3;

ALTER VIEW public.v_plaintiff_discount_rank SET (security_invoker = true);

-- Materialized views cannot have RLS policies directly; lock down direct
-- SELECT to service_role (matches every other cache/index table in this
-- migration set) and expose the ranked view (security_invoker, no anon
-- grant here either — the /plaintiffs page reads through the MCP service
-- role, not directly from PostgREST as anon).
REVOKE ALL ON public.plaintiff_discount_index FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.plaintiff_discount_index TO service_role;
REVOKE ALL ON public.v_plaintiff_discount_rank FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.v_plaintiff_discount_rank TO service_role;

-- Top-25 leaderboard for the planned biddeed.ai/plaintiffs page (that page
-- itself lives in the separate biddeed-ai-ui repo, out of scope for this
-- dispatch per M5 — this RPC is the data contract it will call). anon can
-- execute since this is a public, decision-support scoreboard with no PII —
-- same publication posture as the rest of the marketing site.
CREATE OR REPLACE FUNCTION public.get_plaintiff_discount_leaderboard()
RETURNS TABLE (
  plaintiff_norm text,
  n_third_party_sales bigint,
  median_sold_to_judgment numeric,
  min_sold_to_judgment numeric,
  third_party_share numeric,
  rank_by_discount bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT plaintiff_norm, n_third_party_sales, median_sold_to_judgment,
         min_sold_to_judgment, third_party_share, rank_by_discount
  FROM public.v_plaintiff_discount_rank
  ORDER BY n_third_party_sales DESC
  LIMIT 25;
$$;

GRANT EXECUTE ON FUNCTION public.get_plaintiff_discount_leaderboard() TO anon, authenticated, service_role;
