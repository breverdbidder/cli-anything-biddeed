-- Migration: county RealTDM MCA upsert infrastructure
-- Applied: 2026-06-19 via Supabase Management API (direct, not supabase db push)
-- Scope: generalized RealTDM scraper support for holmes, walton, santa_rosa, st_johns
--
-- This file documents two functions applied directly to the live Supabase project.
-- They extend the existing brevard-only RealTDM pipeline to any RealTDM-hosted county.

-- ─────────────────────────────────────────────────────────────────────────────
-- FUNCTION 1: touch_county_freshness
-- Updates last_seen_at on multi_county_auctions rows for a given county
-- after a successful RealTDM sweep.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.touch_county_freshness(p_county text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE public.multi_county_auctions
  SET    last_seen_at = now()
  WHERE  lower(county) = lower(p_county);
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- FUNCTION 2: upsert_county_realtdm_mca
-- Upserts a batch of RealTDM case cards into multi_county_auctions.
-- Replaces upsert_brevard_realtdm_cases (Brevard-only) with a county-aware version.
--
-- Parameters:
--   p_county  TEXT   — county slug (e.g. 'holmes', 'walton', 'santa_rosa', 'st_johns')
--   p         JSONB  — array of case objects with fields:
--                       case_number, tdm_case_id, account_number, app_number,
--                       case_status, sale_date, surplus_balance, date_created
--
-- Conflict target: (case_number, county) — updates all mutable fields on conflict.
-- Also calls touch_county_freshness to record sweep timestamp.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.upsert_county_realtdm_mca(p_county text, p jsonb)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  rec jsonb;
BEGIN
  FOR rec IN SELECT * FROM jsonb_array_elements(p)
  LOOP
    INSERT INTO public.multi_county_auctions (
      case_number,
      county,
      tdm_case_id,
      account_number,
      app_number,
      case_status,
      sale_date,
      surplus_balance,
      date_created,
      last_seen_at
    ) VALUES (
      rec->>'case_number',
      lower(p_county),
      rec->>'tdm_case_id',
      rec->>'account_number',
      rec->>'app_number',
      rec->>'case_status',
      NULLIF(rec->>'sale_date', '')::date,
      rec->>'surplus_balance',
      NULLIF(rec->>'date_created', '')::date,
      now()
    )
    ON CONFLICT (case_number, county) DO UPDATE SET
      tdm_case_id    = EXCLUDED.tdm_case_id,
      account_number = EXCLUDED.account_number,
      app_number     = EXCLUDED.app_number,
      case_status    = EXCLUDED.case_status,
      sale_date      = EXCLUDED.sale_date,
      surplus_balance = EXCLUDED.surplus_balance,
      date_created   = EXCLUDED.date_created,
      last_seen_at   = now();
  END LOOP;

  PERFORM public.touch_county_freshness(p_county);
END;
$$;

-- Grant execute to service role (used by scraper via REST API)
GRANT EXECUTE ON FUNCTION public.touch_county_freshness(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.upsert_county_realtdm_mca(text, jsonb) TO service_role;
