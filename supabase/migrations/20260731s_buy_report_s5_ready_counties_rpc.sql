-- /buy-report county picker was showing every Gold-Standard-certified county,
-- including ones that lost co_no parcel confirmation (or never had it) — a
-- customer buying a report there gets a partial S5 card (no Shapira Max Bid,
-- no ML prediction, no ZoneWise). Full S5 requires BOTH certified=true AND
-- co_no is_confirmed=true. This RPC is the single source of truth for that
-- intersection so the worker doesn't hand-roll it per endpoint.
--
-- upcoming_count/next_auction_date are scoped to parity_status='matched_clean'
-- to match the same bar predict_auction_outcome's CERT_REQUIRED gate holds —
-- a report bought here must never be for an auction the Shapira pipeline
-- would refuse to analyze.
CREATE OR REPLACE FUNCTION public.get_s5_ready_counties()
RETURNS TABLE(county_slug text, upcoming_count bigint, next_auction_date date)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    g.county_slug,
    COUNT(mca.id) FILTER (
      WHERE mca.auction_date >= CURRENT_DATE
        AND mca.auction_status = 'upcoming'
        AND mca.parity_status = 'matched_clean'
    ) AS upcoming_count,
    MIN(mca.auction_date) FILTER (
      WHERE mca.auction_date >= CURRENT_DATE
        AND mca.auction_status = 'upcoming'
        AND mca.parity_status = 'matched_clean'
    ) AS next_auction_date
  FROM gold_standard_certifications g
  JOIN county_co_no_resolution cno
    ON cno.county_slug = g.county_slug AND cno.is_confirmed = true
  LEFT JOIN multi_county_auctions mca ON mca.county = g.county_slug
  WHERE g.certified = true
  GROUP BY g.county_slug
  HAVING COUNT(mca.id) FILTER (
    WHERE mca.auction_date >= CURRENT_DATE
      AND mca.auction_status = 'upcoming'
      AND mca.parity_status = 'matched_clean'
  ) > 0
  ORDER BY upcoming_count DESC;
$$;

GRANT EXECUTE ON FUNCTION public.get_s5_ready_counties() TO anon;
