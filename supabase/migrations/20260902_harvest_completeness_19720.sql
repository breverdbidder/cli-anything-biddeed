-- Issue #19720 — Harvest Completeness (Phase 0/1/3/4)
-- Applied live via mgmt_sql.py (Supabase Management API) — SUPABASE_DB_PASSWORD/psql is a
-- known-stale path in this environment (see docs/spec/19716.md, decision_log 169/205/287).

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 0: harvest_runs — per-run log, one row per harvest execution
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.harvest_runs (
  id BIGSERIAL PRIMARY KEY,
  mechanism TEXT NOT NULL,                 -- e.g. 'direct_ajax_login', 'firecrawl_actions', 'realtdm_public_portal'
  provider TEXT,                           -- script path that ran it
  county TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('realforeclose','realtaxdeed','realtdm','clerk')),
  sale_date DATE,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  login_ok BOOLEAN,
  scheduled INTEGER,
  with_result INTEGER,
  rows_written INTEGER,
  error TEXT,
  gha_run_id TEXT
);
ALTER TABLE public.harvest_runs ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_harvest_runs_county_platform ON public.harvest_runs(county, platform, started_at DESC);

COMMENT ON TABLE public.harvest_runs IS 'Issue #19720 Phase 0 — measure-first run log for every harvest execution (login_ok/scheduled/with_result/error), replaces trusting a green GHA run as proof of progress.';

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 1: harvest_quarantine — copy of rows whose winning_bidder/sold_amount
-- violated the future-dated-winner guard, plus the reason
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.harvest_quarantine (
  id BIGSERIAL PRIMARY KEY,
  mca_id UUID NOT NULL,
  county TEXT,
  case_number TEXT,
  auction_date DATE,
  offending_winning_bidder TEXT,
  offending_sold_amount NUMERIC,
  reason TEXT NOT NULL,
  quarantined_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.harvest_quarantine ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.harvest_quarantine IS 'Issue #19720 Phase 1 — rows whose winning_bidder/sold_amount write was rejected/NULLed by trg_no_future_winner because auction_date > now() ET.';

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 1: terminal sale_result on multi_county_auctions
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.multi_county_auctions
  ADD COLUMN IF NOT EXISTS sale_result TEXT
    CHECK (sale_result IN ('SOLD_THIRD_PARTY','SOLD_PLAINTIFF','NO_SALE','CANCELLED','REDEEMED','PENDING')),
  ADD COLUMN IF NOT EXISTS sale_result_at TIMESTAMPTZ;

COMMENT ON COLUMN public.multi_county_auctions.sale_result IS 'Issue #19720 Phase 1 — terminal outcome derived from winning_bidder/auction_status/parity_status/case_status. Completeness signal replacing winning_bidder-alone.';
COMMENT ON COLUMN public.multi_county_auctions.sale_result_at IS 'Issue #19720 Phase 1 — when sale_result was last derived/written, for time-to-result measurement.';

-- Backfill: derive from existing signals. Only touches rows with auction_date <= today
-- (future rows get NULL sale_result, not PENDING, since they have not happened yet).
UPDATE public.multi_county_auctions
SET sale_result = CASE
    WHEN parity_status = 'CLERK_SSOT_CANCELLED' THEN 'CANCELLED'
    WHEN auction_status ilike '%cancel%' THEN 'CANCELLED'
    WHEN auction_status = 'redeemed' THEN 'REDEEMED'
    WHEN winning_bidder ilike '3rd party%' OR (winning_bidder IS NOT NULL AND winning_bidder NOT IN ('Plaintiff','Cert Holder') AND winning_bidder NOT ILIKE '%plaintiff%') THEN 'SOLD_THIRD_PARTY'
    WHEN winning_bidder IN ('Plaintiff','Cert Holder') OR winning_bidder ilike '%plaintiff%' THEN 'SOLD_PLAINTIFF'
    WHEN auction_status = 'sold to plaintiff' THEN 'SOLD_PLAINTIFF'
    ELSE 'PENDING'
  END,
  sale_result_at = now()
WHERE auction_date <= current_date
  AND sale_result IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 1: future-dated winner guard — no winning_bidder/sold_amount write
-- where auction_date > now() at time zone 'America/New_York'
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.trg_no_future_winner()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.auction_date > (now() AT TIME ZONE 'America/New_York')::date
     AND (NEW.winning_bidder IS NOT NULL OR NEW.sold_amount IS NOT NULL) THEN
    RAISE EXCEPTION 'harvest_completeness guard: cannot write winning_bidder/sold_amount for auction_date % (future, ET today=%)',
      NEW.auction_date, (now() AT TIME ZONE 'America/New_York')::date
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS no_future_winner ON public.multi_county_auctions;
CREATE TRIGGER no_future_winner
  BEFORE INSERT OR UPDATE OF winning_bidder, sold_amount ON public.multi_county_auctions
  FOR EACH ROW
  EXECUTE FUNCTION public.trg_no_future_winner();

-- Quarantine existing violators, then NULL the offending fields on the live row.
INSERT INTO public.harvest_quarantine (mca_id, county, case_number, auction_date, offending_winning_bidder, offending_sold_amount, reason)
SELECT id, county, case_number, auction_date, winning_bidder, sold_amount,
       'future-dated winner backfill, issue #19720 Phase 1'
FROM public.multi_county_auctions
WHERE (winning_bidder IS NOT NULL OR sold_amount IS NOT NULL)
  AND auction_date > (now() AT TIME ZONE 'America/New_York')::date
  AND NOT EXISTS (
    SELECT 1 FROM public.harvest_quarantine q WHERE q.mca_id = multi_county_auctions.id
  );

-- Null via a session var so the trigger (fires on this UPDATE too) doesn't block the cleanup.
ALTER TABLE public.multi_county_auctions DISABLE TRIGGER no_future_winner;
UPDATE public.multi_county_auctions
SET winning_bidder = NULL, sold_amount = NULL, sale_result = 'PENDING'
WHERE id IN (SELECT mca_id FROM public.harvest_quarantine WHERE reason = 'future-dated winner backfill, issue #19720 Phase 1');
ALTER TABLE public.multi_county_auctions ENABLE TRIGGER no_future_winner;

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 3: fix upsert_county_realtdm_mca — the columns it writes
-- (tdm_case_id/account_number/app_number/case_status/sale_date/surplus_balance/
-- date_created) never existed on multi_county_auctions and ON CONFLICT
-- (case_number, county) has no matching unique constraint (the real one is
-- (county, case_number, sale_type)) -- every call has errored since 2026-06-19.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.multi_county_auctions
  ADD COLUMN IF NOT EXISTS tdm_case_id TEXT,
  ADD COLUMN IF NOT EXISTS account_number TEXT,
  ADD COLUMN IF NOT EXISTS app_number TEXT,
  ADD COLUMN IF NOT EXISTS case_status TEXT,
  ADD COLUMN IF NOT EXISTS sale_date DATE,
  ADD COLUMN IF NOT EXISTS surplus_balance TEXT,
  ADD COLUMN IF NOT EXISTS date_created DATE;

COMMENT ON COLUMN public.multi_county_auctions.case_status IS 'Issue #19720 Phase 3 — raw RealTDM case status string (e.g. ACTIVE - SOLD BIDDER, COMPLETED - REDEEMED), mapped to sale_result by upsert_county_realtdm_mca.';

DROP FUNCTION IF EXISTS public.upsert_county_realtdm_mca(text, jsonb);
CREATE FUNCTION public.upsert_county_realtdm_mca(p_county text, p jsonb)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  rec jsonb;
  v_case_number text;
  v_status text;
  v_result text;
BEGIN
  FOR rec IN SELECT * FROM jsonb_array_elements(p)
  LOOP
    v_case_number := rec->>'case_number';
    v_status := rec->>'case_status';
    v_result := CASE
      WHEN v_status ILIKE '%REDEEMED%' THEN 'REDEEMED'
      WHEN v_status ILIKE '%CANCEL%' THEN 'CANCELLED'
      WHEN v_status ILIKE '%SOLD BIDDER%' THEN 'SOLD_THIRD_PARTY'
      WHEN v_status ILIKE '%SOLD%' THEN 'SOLD_THIRD_PARTY'
      WHEN v_status ILIKE '%NO SALE%' OR v_status ILIKE '%NO-SALE%' THEN 'NO_SALE'
      WHEN v_status ILIKE 'ACTIVE%' THEN 'PENDING'
      ELSE NULL
    END;

    UPDATE public.multi_county_auctions SET
      tdm_case_id     = rec->>'tdm_case_id',
      account_number  = rec->>'account_number',
      app_number      = rec->>'app_number',
      case_status     = v_status,
      sale_date       = NULLIF(rec->>'sale_date', '')::date,
      surplus_balance = rec->>'surplus_balance',
      date_created    = NULLIF(rec->>'date_created', '')::date,
      sale_result     = COALESCE(v_result, sale_result),
      sale_result_at  = CASE WHEN v_result IS NOT NULL THEN now() ELSE sale_result_at END,
      parity_status   = CASE WHEN v_status ILIKE '%REDEEMED%' THEN 'REALTDM_REDEEMED'
                              WHEN v_status ILIKE '%CANCEL%' THEN 'REALTDM_CANCELLED'
                              ELSE parity_status END,
      last_seen_at    = now()
    WHERE lower(county) = lower(p_county) AND case_number = v_case_number AND sale_type = 'tax_deed';

    IF NOT FOUND THEN
      INSERT INTO public.multi_county_auctions (
        case_number, county, sale_type, tdm_case_id, account_number, app_number,
        case_status, sale_date, surplus_balance, date_created, sale_result, sale_result_at,
        auction_date, last_seen_at
      ) VALUES (
        v_case_number, lower(p_county), 'tax_deed', rec->>'tdm_case_id', rec->>'account_number', rec->>'app_number',
        v_status, NULLIF(rec->>'sale_date','')::date, rec->>'surplus_balance', NULLIF(rec->>'date_created','')::date,
        COALESCE(v_result, 'PENDING'), CASE WHEN v_result IS NOT NULL THEN now() END,
        NULLIF(rec->>'sale_date','')::date, now()
      )
      ON CONFLICT (county, case_number, sale_type) DO UPDATE SET
        tdm_case_id     = EXCLUDED.tdm_case_id,
        account_number  = EXCLUDED.account_number,
        app_number      = EXCLUDED.app_number,
        case_status     = EXCLUDED.case_status,
        sale_date       = EXCLUDED.sale_date,
        surplus_balance = EXCLUDED.surplus_balance,
        date_created    = EXCLUDED.date_created,
        sale_result     = COALESCE(EXCLUDED.sale_result, public.multi_county_auctions.sale_result),
        last_seen_at    = now();
    END IF;
  END LOOP;

  PERFORM public.touch_county_freshness(p_county);
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_county_realtdm_mca(text, jsonb) TO service_role;

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 4: completeness SSOT views
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_harvest_completeness
WITH (security_invoker = true) AS
SELECT
  county,
  sale_type,
  auction_date AS sale_date,
  count(*) AS scheduled_total,
  count(*) FILTER (WHERE sale_result IN ('CANCELLED','REDEEMED')) AS excluded,
  count(*) FILTER (WHERE sale_result NOT IN ('CANCELLED','REDEEMED')) AS scheduled,
  count(*) FILTER (WHERE sale_result NOT IN ('CANCELLED','REDEEMED','PENDING') AND sale_result IS NOT NULL) AS with_result,
  ROUND(
    100.0 * count(*) FILTER (WHERE sale_result NOT IN ('CANCELLED','REDEEMED','PENDING') AND sale_result IS NOT NULL)
    / NULLIF(count(*) FILTER (WHERE sale_result NOT IN ('CANCELLED','REDEEMED')), 0), 1
  ) AS pct,
  ROUND(
    AVG(EXTRACT(EPOCH FROM (sale_result_at - (auction_date::timestamptz))) / 3600.0)
      FILTER (WHERE sale_result NOT IN ('CANCELLED','REDEEMED','PENDING') AND sale_result IS NOT NULL), 1
  ) AS median_hours_to_result
FROM public.multi_county_auctions
WHERE auction_date IS NOT NULL AND auction_date <= current_date
GROUP BY county, sale_type, auction_date;

COMMENT ON VIEW public.v_harvest_completeness IS 'Issue #19720 Phase 4 — county x sale_type x sale_date completeness SSOT. pct excludes CANCELLED/REDEEMED from the denominator per the approved intent formula.';

CREATE OR REPLACE VIEW public.v_harvest_completeness_30d
WITH (security_invoker = true) AS
SELECT
  county,
  sale_type,
  SUM(scheduled_total) AS scheduled_total,
  SUM(excluded) AS excluded,
  SUM(scheduled) AS scheduled,
  SUM(with_result) AS with_result,
  ROUND(100.0 * SUM(with_result) / NULLIF(SUM(scheduled), 0), 1) AS pct
FROM public.v_harvest_completeness
WHERE sale_date >= current_date - interval '30 day'
GROUP BY county, sale_type;

COMMENT ON VIEW public.v_harvest_completeness_30d IS 'Issue #19720 Phase 4 — 30-day rollup of v_harvest_completeness, feeds D0/SPI daily report and the D6 watchdog.';

-- ─────────────────────────────────────────────────────────────────────────────
-- PHASE 4: golden set skeleton (population is a separate, evidence-gated step)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.harvest_golden_set (
  id BIGSERIAL PRIMARY KEY,
  county TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('realforeclose','realtaxdeed','realtdm')),
  case_number TEXT NOT NULL,
  expected_sale_result TEXT NOT NULL CHECK (expected_sale_result IN ('SOLD_THIRD_PARTY','SOLD_PLAINTIFF','NO_SALE','CANCELLED','REDEEMED')),
  expected_winner TEXT,
  expected_amount NUMERIC,
  verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  verified_source TEXT NOT NULL,
  UNIQUE (county, platform, case_number)
);
ALTER TABLE public.harvest_golden_set ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.harvest_golden_set IS 'Issue #19720 Phase 4 — hand-verified golden set (target 50 rows / 10 counties / all 3 platforms). harvest_golden_check() re-harvests and diffs against this table.';
