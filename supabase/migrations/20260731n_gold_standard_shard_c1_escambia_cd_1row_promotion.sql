-- ESCAMBIA C/D fix — dispatch ca56cc4d-4e7f-4234-814f-a1e6de065d52, SHARD-C1, 2026-07-31
--
-- Context: this session already applied the promotion below live via PostgREST
-- (service-role key, bypassing RLS) as part of the diagnosis-first workflow. This
-- SQL is provided as an idempotent, re-runnable record of that write (safe to
-- re-execute — it only promotes rows that are still parity_status IS NULL and
-- match the exact, live-verified case number).
--
-- Root cause of the persistent 87.8-88.3% ceiling across many prior sessions
-- (shard1/shard3/shard11/shard13/shard14/run20260724): NOT a parity-source
-- tagging bug (unlike st_lucie's tier1_realforeclose rename bug) and NOT a
-- scraper/Turnstile block. All 353-354 currently-matched rows already carry
-- correctly-prefixed tier1_* sources. The ~46-47 row gap is 100% composed of
-- far-future tax_deed calendar_sweep_mca_v3 rows (auction dates 09/02, 10/07,
-- 11/04, 12/02/2026) whose stored case numbers have zero exact overlap with
-- the live RealTaxDeed listing for the same dates (60 items/date, confirmed
-- live this session) — a genuine upstream TD-certificate substitution/
-- redemption divergence between our calendar-sweep source and RealAuction's
-- current list, reconfirmed on top of 4+ prior independent harvests
-- (shard13, shard14, shard3_run6046, run20260724) that found the same
-- structural residual after promoting whatever few exact matches existed at
-- the time. This session's harvest closed 1 additional row (the lone
-- foreclosure entry on 08/13/2026, which is now close enough to post) and
-- reconfirmed the tax_deed residual is unchanged in kind.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realauction_escambia_run20260731_ca56cc4d'
WHERE county = 'escambia'
  AND parity_status IS NULL
  AND case_number = '2025 CA 000855';

COMMIT;

-- Verification:
-- SELECT count(*) FROM public.multi_county_auctions
--  WHERE county='escambia' AND parity_status='matched_clean'
--    AND parity_source LIKE 'tier1%';
-- Expected: 354 (was 353 before this session)
