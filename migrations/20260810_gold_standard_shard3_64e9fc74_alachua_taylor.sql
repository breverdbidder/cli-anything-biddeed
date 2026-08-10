-- GOLD STANDARD SHARD-3 (dispatch 64e9fc74, loop run 10213)
-- Counties: alachua (E/I), taylor (B/F re-confirm)
-- Session: 2026-08-10T08:00Z
-- Issue: breverdbidder/cli-anything-biddeed#18533
--
-- This migration is the audit record for the shard3-run10213-alachua-ei-taylor
-- workflow run. The actual DML is executed live by
-- scripts/shard3_run10213_alachua_ei_taylor_closeout.py via the Management API.
--
-- SUMMARY OF OUTCOMES:
--   alachua: 8/10 (E=93.0%, I=87.3%) — diagnosis + enrichment attempt
--     E: new rows since run 6253 checked via RealForeclose AJAX
--        Prior dead-end set (8 cases) re-confirmed unresolvable without fabrication
--     I: card-incomplete rows with real parcel_ids enriched via ArcGIS Parcels35_view
--        (lat/lon centroid + JustValue + zoning_districts/parcel_zones link)
--   taylor: 8/10 (B=null, F=null) — B/F confirmed blocked (4th+ session)
--     KMA API: taylorclerk.com/wp-json/kma/v1/ active-cases-only feed re-checked
--     Closed cases hard-deleted server-side on sale; no sold_amount data obtainable
--     pubrecords.taylorclerk.com: Cloudflare 403 (confirmed 3 prior sessions)
--     qpublic.schneidercorp.com: 403 Cloudflare
--     FL GIO NAL: annual refresh, pre-sale ownership data only
--
-- HARD GUARDRAILS COMPLIANCE:
--   - PropertyOnion data NOT touched (never a source, litmus only)
--   - No cron jobs 109/111/115 or gold-standard-loop-* modified
--   - Schema changes (if any) via this migration file only
--   - No parcel_zones rows for zone_codes lacking zoning_districts catalog entries
--     (would zero out G for sparse counties — see 20260806 migration lesson)

-- ── Session close-out ultraloop audit record ──
-- This INSERT is idempotent (ON CONFLICT DO NOTHING).
-- The full audit trail for individual letter claims is written by
-- scripts/shard3_run10213_alachua_ei_taylor_closeout.py.
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES (
  '64e9fc74-9394-4c46-96bd-e7d8f6d6a949',
  'fallback',
  'session',
  'closeout',
  'SHARD-3 run10213 session migration committed — alachua E/I enrichment + taylor B/F re-confirm',
  '{"counties": ["alachua", "taylor"], "alachua_baseline": {"E": "93.0", "I": "87.3"}, "taylor_baseline": {"B": "null", "F": "null"}, "script": "scripts/shard3_run10213_alachua_ei_taylor_closeout.py", "workflow": ".github/workflows/shard3-run10213-alachua-ei-taylor.yml"}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;
