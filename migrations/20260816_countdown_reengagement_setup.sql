-- Countdown-based re-engagement: match auction_llc_expansion leads to
-- upcoming auctions in their historical county, schedule T-14/T-7/T-3 sends.
-- Task: countdown_reengagement_setup
--
-- lead_profiles.county is already the lead's historical county (populated by
-- the auction_llc_expansion ingest — no join back to multi_county_auctions on
-- winning_bidder is needed, the county is already denormalized onto the row).
--
-- Match strategy: ONE row per lead = their single NEAREST upcoming auction in
-- their county (not every auction in the 30d window). A county-level match
-- against a 30-day window returns ~30 auctions per lead on average; emailing
-- an LLC lead a T-14 countdown for 30 unrelated auctions simultaneously is
-- spam, not re-engagement. Nearest-auction keeps this "a new small table"
-- (per the brief's own wording) and keeps the send volume sane. As time
-- passes and today's near-term auctions fall off the 30-day window, re-running
-- this population query naturally rolls forward to the next nearest auction.
--
-- "Real upcoming" excludes auction_status IN ('redeemed','cancelled','CANCELLED',
-- 'canceled','stayed','pending_verification','preview') — those are not live
-- auctions even though sold_amount is still NULL on them (sold_amount alone is
-- a known-unreliable freshness signal per the gold-standard skill corpus;
-- redeemed cases in particular resolved before sale and must not be emailed
-- as "upcoming").
--
-- No FK constraints to lead_profiles/multi_county_auctions: both are hot
-- tables under constant pg_cron write load (see `cron.job`) and ADD CONSTRAINT
-- FOREIGN KEY needs a lock neither can hand out promptly. Referential
-- integrity is enforced at write time by the populate query + send script,
-- which both join against the live tables directly.

CREATE TABLE IF NOT EXISTS public.lead_auction_countdown (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lead_id        uuid NOT NULL,
  auction_id     uuid NOT NULL,
  county         text NOT NULL,
  auction_date   date NOT NULL,
  send_t14_at    timestamptz NOT NULL,
  send_t7_at     timestamptz NOT NULL,
  send_t3_at     timestamptz NOT NULL,
  t14_sent       boolean NOT NULL DEFAULT false,
  t7_sent        boolean NOT NULL DEFAULT false,
  t3_sent        boolean NOT NULL DEFAULT false,
  t14_sent_at    timestamptz,
  t7_sent_at     timestamptz,
  t3_sent_at     timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (lead_id, auction_id)
);

CREATE INDEX IF NOT EXISTS idx_lead_auction_countdown_due
  ON public.lead_auction_countdown (auction_date)
  WHERE NOT (t14_sent AND t7_sent AND t3_sent);

ALTER TABLE public.lead_auction_countdown ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy WHERE polname = 'lead_auction_countdown_service_only'
  ) THEN
    CREATE POLICY lead_auction_countdown_service_only
      ON public.lead_auction_countdown FOR ALL USING (false);
  END IF;
END $$;

-- Idempotent backfill: nearest live upcoming auction per lead, in-county.
WITH leads AS (
  SELECT id, county
  FROM public.lead_profiles
  WHERE source = 'auction_llc_expansion'
    AND county IS NOT NULL
),
auctions AS (
  SELECT id, county, auction_date
  FROM public.multi_county_auctions
  WHERE auction_date >= CURRENT_DATE
    AND auction_date <= CURRENT_DATE + INTERVAL '30 days'
    AND sold_amount IS NULL
    AND auction_status IN ('upcoming', 'scheduled')
),
nearest AS (
  SELECT DISTINCT ON (l.id)
    l.id AS lead_id, a.id AS auction_id, a.county, a.auction_date
  FROM leads l
  JOIN auctions a ON a.county = l.county
  ORDER BY l.id, a.auction_date ASC, a.id ASC
)
INSERT INTO public.lead_auction_countdown
  (lead_id, auction_id, county, auction_date, send_t14_at, send_t7_at, send_t3_at)
SELECT
  lead_id, auction_id, county, auction_date,
  (auction_date - INTERVAL '14 days') + TIME '13:00:00',
  (auction_date - INTERVAL '7 days')  + TIME '13:00:00',
  (auction_date - INTERVAL '3 days')  + TIME '13:00:00'
FROM nearest
ON CONFLICT (lead_id, auction_id) DO NOTHING;

-- Daily trigger: pg_cron cannot hold RESEND_API_KEY (third-party secret, no
-- vault allow-list entry per CLAUDE.md CREDENTIAL HANDLING) so it bridges to
-- the GHA workflow via the existing fire_workflow_dispatch() sanctioned path
-- (same pattern as jobid 226 gha-zonewise-100-hourly) — the actual send runs
-- inside the GHA runner env: block where RESEND_API_KEY is masked.
SELECT cron.schedule(
  'countdown-reengagement-daily',
  '0 13 * * *',
  $cron$SELECT public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','countdown-reengagement-send.yml','main','{}'::jsonb);$cron$
);
