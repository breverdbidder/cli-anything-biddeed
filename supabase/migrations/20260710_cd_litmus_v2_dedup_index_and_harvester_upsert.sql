-- C/D LITMUS V2 (issue #10981 / #11366 follow-up) — document the live dedup index
-- and fix the harvester scripts that it silently broke.
--
-- ROOT CAUSE (VERIFIED live 2026-07-10): ux_parity_v2_county_src_sale (UNIQUE on
-- county_slug, source, sale_type) exists live on cd_litmus_parity_v2 but was never
-- committed to supabase/migrations/ (same "created ad hoc via Management API, never
-- checked in" gap 20260706_cd_litmus_v2_tables.sql already called out for the base
-- tables). This migration is a no-op against the live DB (IF NOT EXISTS) but gives
-- the schema a reproducible source of truth.
--
-- That undocumented index has a real consequence: all three harvester scripts
-- (scripts/cd_litmus_v2_realauction_parity.py, cd_litmus_v2_realauction_harvest.py,
-- cd_litmus_v2_floridabidder_fallback.py) do a plain INSERT with no ON CONFLICT
-- clause. Since the index was added, every re-harvest of a (county, source,
-- sale_type) combo already seen once has been failing with 23505 duplicate-key —
-- confirmed live by re-running cd_litmus_v2_realauction_parity.py this session and
-- observing "ERROR: duplicate key value violates unique constraint
-- ux_parity_v2_county_src_sale" on every insert. cd_litmus_parity_v2 has been stuck
-- at its 2026-07-09T17:29:49Z batch (36 rows) ever since, silently, through two
-- prior redispatches of issue #11366 (GHA runs 29056140756, 29048698178) — which is
-- why gold_standard_loop's v2-sourced C/D gain count never moved past the single
-- hillsborough/D flip found on 2026-07-09, no matter how many times the loop/certify
-- were re-run: re-scoring stale data can't produce new gains.
--
-- FIX (in the .py files, not SQL): all three scripts now INSERT ... ON CONFLICT
-- (county_slug, source, sale_type) DO UPDATE, matching the "one current row per
-- combo, freshest wins" semantics the unique index and
-- pencil_dod_evaluate_county_v2()'s "latest row per source" read already assume.
-- This migration only documents the index; the behavioral fix is the .py diff.

CREATE UNIQUE INDEX IF NOT EXISTS ux_parity_v2_county_src_sale
  ON public.cd_litmus_parity_v2 (county_slug, source, sale_type);

COMMENT ON INDEX public.ux_parity_v2_county_src_sale IS
  'One current row per (county_slug, source, sale_type) -- harvester scripts upsert '
  '(ON CONFLICT DO UPDATE) into this key, refreshing fetched_at/status/counts in '
  'place rather than accumulating history. pencil_dod_evaluate_county_v2() relies on '
  'this being the single live row per combo.';
