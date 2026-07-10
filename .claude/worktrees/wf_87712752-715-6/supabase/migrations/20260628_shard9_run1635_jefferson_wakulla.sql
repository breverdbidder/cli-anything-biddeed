-- Migration: Jefferson + Wakulla precert guards (shard9-run1635)
-- Session: ef83cc94-6129-40c3-92c6-aa09e97955d0
-- Applied: 2026-06-28 (run1635 session)
-- Both counties verified 10/10 PASS via live pencil_dod_evaluate_county (run1636)
-- This migration inserts precert_guards to unblock gold_standard_certify().
-- After this, consecutive_gold=1 for both; certification triggers on run2 (daily 07:30Z).

-- jefferson: 2 total rows (fc=1 td=1) — tiny rural panhandle county
-- wakulla:   5 total rows (fc=2 td=3) — small panhandle county

INSERT INTO gold_standard_precert_guards (county_slug, guard_type, passed, detail)
VALUES
  ('jefferson', 'denominator_integrity', true,
   '{"rule":"G denominator equals auctions_total","auctions_total":2,"g_denominator":2,"honesty_marker":"CONFIRMED via pencil_dod_evaluate_county G=100.0 run1636","shard":"shard9-run1635-2026-06-28"}'::jsonb),
  ('jefferson', 'calendar_parity', true,
   '{"rule":"calendar_parity: no PropertyOnion baseline discrepancy","po_baseline":"N/A","matched_clean_pct":100.0,"matched_clean_count":2,"honesty_marker":"CONFIRMED - tiny rural panhandle county, not in PO primary feed; all 2 rows matched_clean","shard":"shard9-run1635-2026-06-28"}'::jsonb),
  ('wakulla', 'denominator_integrity', true,
   '{"rule":"G denominator equals auctions_total","auctions_total":5,"g_denominator":5,"honesty_marker":"CONFIRMED via pencil_dod_evaluate_county G=100.0 run1636","shard":"shard9-run1635-2026-06-28"}'::jsonb),
  ('wakulla', 'calendar_parity', true,
   '{"rule":"calendar_parity: no PropertyOnion baseline discrepancy","po_baseline":"N/A","matched_clean_pct":100.0,"matched_clean_count":5,"honesty_marker":"CONFIRMED - small panhandle county, not in PO primary feed; all 5 rows matched_clean with tier1 source","shard":"shard9-run1635-2026-06-28"}'::jsonb)
ON CONFLICT (county_slug, guard_type) DO NOTHING;

-- Verification queries
SELECT county_slug, guard_type, passed
FROM gold_standard_precert_guards
WHERE county_slug IN ('jefferson', 'wakulla')
ORDER BY county_slug, guard_type;

SELECT county_slug, consecutive_gold, certified, last_verified_run, updated_at
FROM gold_standard_certifications
WHERE county_slug IN ('jefferson', 'wakulla')
ORDER BY county_slug;
