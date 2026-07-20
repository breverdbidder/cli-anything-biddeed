-- MAXBID SWEEP (issue #12854): observation history for RealAuction's
-- "Plaintiff Max Bid" field, which is publicly disclosed on the rendered
-- auction page only during an early-morning visibility window and reads
-- "Hidden" once the window closes (field-proven, Marion 2026-07-20:
-- disclosed at 11:56Z, "Hidden" for all 4 cases by 12:10Z and still
-- "Hidden" live at 13:15Z when this migration was authored).
--
-- New additive table: every capture attempt (value OR hidden) appends a
-- row here. Revisions are signal -- a later "Hidden" does not erase an
-- earlier disclosed number, both rows persist.
--
-- New additive column on multi_county_auctions: plaintiff_max_bid_observed_at,
-- stamped only when a sweep writes a real (non-hidden) value. The existing
-- plaintiff_max_bid / plaintiff_max_bid_source columns (landed under #12851)
-- are untouched by this migration; the maxbid sweep script reuses them via
-- the same columns-scoped, non-destructive upsert pattern calendar_sweep_mca.py
-- already uses for opening_bid/judgment_amount (never let a NULL/Hidden
-- observation participate in a DO UPDATE SET that would null out a
-- previously-disclosed value).

CREATE TABLE IF NOT EXISTS public.mca_maxbid_observations (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_number   text NOT NULL,
  county        text NOT NULL,
  observed_at   timestamptz NOT NULL,
  value         numeric,
  is_hidden     boolean NOT NULL,
  source_path   text NOT NULL,
  sweep_run_id  text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT mca_maxbid_observations_value_check
    CHECK ( (is_hidden AND value IS NULL) OR (NOT is_hidden AND value IS NOT NULL) )
);

-- Idempotency key: a sweep re-run within the same minute-bucket for the
-- same case is a no-op, not a duplicate history row. observed_at is
-- pre-bucketed by the sweep script (truncated to the minute) before insert,
-- so this unique index is the actual dedup mechanism -- not asserted, enforced.
CREATE UNIQUE INDEX IF NOT EXISTS mca_maxbid_observations_case_time_uidx
  ON public.mca_maxbid_observations (case_number, county, observed_at);

CREATE INDEX IF NOT EXISTS mca_maxbid_observations_case_idx
  ON public.mca_maxbid_observations (case_number, county);

ALTER TABLE public.multi_county_auctions
  ADD COLUMN IF NOT EXISTS plaintiff_max_bid_observed_at timestamptz;

COMMENT ON TABLE public.mca_maxbid_observations IS
  'MAXBID SWEEP (#12854): timestamped observation history of RealAuction Plaintiff Max Bid captures. Hidden stored as is_hidden=true/value=NULL, never 0. Additive, never rewrite multi_county_auctions directly from here except via the sweep script''s non-destructive projection.';
COMMENT ON COLUMN public.multi_county_auctions.plaintiff_max_bid_observed_at IS
  'MAXBID SWEEP (#12854): timestamp of the most recent non-hidden plaintiff_max_bid observation projected onto this row. NULL if never disclosed to a sweep.';
