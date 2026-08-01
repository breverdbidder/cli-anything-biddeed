-- auto_parity_check_queue() — nightly parity-verification queue, per issue
-- "Scraper: populate auction_url per auction row from RealForeclose/RealTaxDeed".
--
-- Depends on auction_url now being populated (this session backfilled 578
-- rows via the realforeclose_aids AID table + realauction_subdomains, and
-- .github/scripts/calendar_sweep_mca.py now persists auction_url on every
-- future ingest — see that file's upsert_to_mca()). Before this, the brief's
-- own get_parity_remediation_queue() (20260801c) returned 0 rows because
-- auction_url was NULL for 100% of upcoming bad-parity rows.
--
-- last_parity_check is a new column (does not exist yet, confirmed via
-- information_schema.columns) so every row starts NULL and is immediately
-- eligible for a first check.
ALTER TABLE public.multi_county_auctions
  ADD COLUMN IF NOT EXISTS last_parity_check timestamptz;

CREATE OR REPLACE FUNCTION public.auto_parity_check_queue(p_limit int DEFAULT 50)
RETURNS TABLE(id uuid, county text, case_number text, auction_date date, auction_url text)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT id, county, case_number, auction_date, auction_url
  FROM multi_county_auctions
  WHERE auction_date >= CURRENT_DATE
    AND auction_status = 'upcoming'
    AND auction_url IS NOT NULL
    AND (parity_status IS NULL OR parity_status NOT IN ('matched_clean'))
    AND (last_parity_check IS NULL OR last_parity_check < NOW() - INTERVAL '24 hours')
  ORDER BY auction_date ASC
  LIMIT p_limit;
$$;
GRANT EXECUTE ON FUNCTION public.auto_parity_check_queue(int) TO anon;
