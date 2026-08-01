-- Option A architecture change (approved by Ariel Aug 1 2026): Gold Standard
-- certification becomes a data-quality SIGNAL only, never a customer access
-- gate. /buy-report/counties previously called get_s5_ready_counties(), which
-- only returns counties that are BOTH gold_standard_certifications.certified
-- AND county_co_no_resolution.is_confirmed — excluding 52 of the 67 counties
-- that have real upcoming auctions (verified via multi_county_auctions on
-- 2026-08-01) from the $25 report picker entirely.
--
-- This RPC returns every county with an upcoming auction, tagging each with
-- is_gold_standard so the UI can show a badge without gating on it.
CREATE OR REPLACE FUNCTION public.get_all_counties_with_status()
RETURNS TABLE(
  county text,
  county_display text,
  upcoming bigint,
  next_auction date,
  is_gold_standard boolean,
  sale_types text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    mca.county,
    initcap(replace(mca.county, '_', ' ')) as county_display,
    COUNT(*) FILTER (WHERE mca.auction_date >= CURRENT_DATE AND mca.auction_status = 'upcoming') as upcoming,
    MIN(mca.auction_date) FILTER (WHERE mca.auction_date >= CURRENT_DATE AND mca.auction_status = 'upcoming') as next_auction,
    COALESCE(g.certified, false) as is_gold_standard,
    string_agg(DISTINCT mca.sale_type, '+' ORDER BY mca.sale_type) as sale_types
  FROM multi_county_auctions mca
  LEFT JOIN gold_standard_certifications g ON g.county_slug = mca.county
  GROUP BY mca.county, g.certified
  HAVING COUNT(*) FILTER (WHERE mca.auction_date >= CURRENT_DATE AND mca.auction_status = 'upcoming') > 0
  ORDER BY upcoming DESC;
$$;

GRANT EXECUTE ON FUNCTION public.get_all_counties_with_status() TO anon;
