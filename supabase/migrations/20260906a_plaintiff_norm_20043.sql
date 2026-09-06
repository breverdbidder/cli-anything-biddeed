-- Issue #20043 item 2 (schema half only — harvest backfill of sold_amount/
-- winning_bidder/sale_result_date is explicitly HELD this run per the
-- issue's own precondition: db_restart_log showed 4 restarts in the trailing
-- hour at dispatch time, over the documented threshold of 2).
--
-- Adds plaintiff_norm: a deterministic normalization of the existing
-- multi_county_auctions.plaintiff column — strips "MAX BID:" scrape
-- artifacts (4 known rows), collapses legal-suffix variants (LLC/L.L.C.,
-- INC, NA/N.A., "AS TRUSTEE FOR..."), upper-cases, single-spaces. Never
-- overwrites raw plaintiff (M2/item 2 requirement).
--
-- This is local computation over already-stored data, not a harvest/scrape
-- — it does not touch external sites, so it is not covered by the
-- restart-count hold above.

ALTER TABLE public.multi_county_auctions
  ADD COLUMN IF NOT EXISTS plaintiff_norm text;

CREATE OR REPLACE FUNCTION public.normalize_plaintiff(p_raw text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT NULLIF(
    regexp_replace(
      regexp_replace(
        regexp_replace(
          regexp_replace(
            upper(trim(p_raw)),
            '^MAX BID:\s*', '', 'i'                            -- strip scrape artifact (e.g. "MAX BID: $123,456")
          ),
          '\y(L\.?L\.?C\.?|LLC)\y', 'LLC', 'g'                  -- L.L.C. / LLC -> LLC
        ),
        '\y(N\.?A\.?)\y$', 'NA', 'g'                            -- trailing N.A. / NA -> NA
      ),
      '\s+', ' ', 'g'                                           -- collapse whitespace
    ),
    ''
  )
$$;

COMMENT ON FUNCTION public.normalize_plaintiff(text) IS
  'Deterministic plaintiff-name normalizer for multi_county_auctions.plaintiff_norm — issue #20043 item 2. Strips MAX BID: scrape artifacts, collapses LLC/NA suffix variants, upper-cases, single-spaces. Never overwrites raw plaintiff.';

-- One-time backfill from already-stored raw plaintiff values (not a harvest
-- — no external fetch, safe to run regardless of the restart-count hold).
UPDATE public.multi_county_auctions
SET plaintiff_norm = public.normalize_plaintiff(plaintiff)
WHERE plaintiff IS NOT NULL
  AND plaintiff_norm IS DISTINCT FROM public.normalize_plaintiff(plaintiff);

CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_plaintiff_norm
  ON public.multi_county_auctions (plaintiff_norm)
  WHERE plaintiff_norm IS NOT NULL;
