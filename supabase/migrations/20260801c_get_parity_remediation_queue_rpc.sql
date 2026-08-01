-- Parity gate + remediation (issue: block $25 report sales on unverified
-- auctions). This RPC surfaces the upcoming auctions whose parity_status
-- hasn't been cross-checked against the live RealForeclose/RealTaxDeed
-- calendar, so CC/agents can work the remediation queue in bounded batches
-- instead of scanning the full multi_county_auctions table each time.
--
-- Live re-derivation on 2026-08-01 (Management API, multi_county_auctions,
-- auction_status='upcoming' AND auction_date >= CURRENT_DATE) found:
--   matched_clean: 1700, NULL: 229, matched_divergent: 2, mca_only: 0
-- mca_only genuinely-upcoming count is 0, not the brief's 49 — the 1370 rows
-- with parity_status='mca_only' AND auction_status='upcoming' are all stale
-- (auction_date <= 2026-07-31, before today). This RPC's date/status filter
-- naturally excludes them; PART 3 of the brief separately marks them
-- pending_verification so they can't leak into the buy flow if their status
-- ever gets corrected without a fresh parity check.
CREATE OR REPLACE FUNCTION public.get_parity_remediation_queue()
RETURNS TABLE(id uuid, county text, case_number text, auction_date date,
              source_platform text, parity_status text, auction_url text)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT id, county, case_number, auction_date, source_platform, parity_status, auction_url
  FROM multi_county_auctions
  WHERE auction_date >= CURRENT_DATE
    AND auction_status = 'upcoming'
    AND (parity_status IS NULL OR parity_status IN ('mca_only', 'matched_divergent'))
    AND auction_url IS NOT NULL
  ORDER BY auction_date ASC
  LIMIT 50;
$$;
GRANT EXECUTE ON FUNCTION public.get_parity_remediation_queue() TO anon;
