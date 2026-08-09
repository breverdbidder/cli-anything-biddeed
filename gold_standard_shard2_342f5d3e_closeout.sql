-- Gold Standard shard-2 (gulf/gilchrist/union/lake) session close-out
-- dispatch_id 342f5d3e-c31b-4f49-9c84-7a0efdc5f99d, loop run 9906
-- Session: 2026-08-09, architect-20260809T080000
-- Final pencil_dod_evaluate_county() results (fresh, post-workflow):
--   gulf:      9/10 (I fails, blocked_needs_more_research — genuine missing zoning-district assignment for 2 parcels, no source found)
--   gilchrist: 8/10 (E,I fail, blocked_needs_more_research — 6 rows, all official sources Cloudflare/Turnstile/credential-blocked this session)
--   union:     8/10 (B,F fail, blocked_structural — 0 closed sales exist; both foreclosures still upcoming 2026-08-13/2026-10-15, tax deed correctly redeemed not sold)
--   lake:      8/10, UP FROM 6/10 (E and J moved to PASS; C improved 91.5%->94.1% but still fails; I unchanged, fail)
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{
    "gulf":      {"A": true, "B": true, "C": true, "D": true, "E": true, "F": true, "G": true, "H": true, "I": false, "J": true},
    "gilchrist": {"A": true, "B": true, "C": true, "D": true, "E": false, "F": true, "G": true, "H": true, "I": false, "J": true},
    "union":     {"A": true, "B": false, "C": true, "D": true, "E": true, "F": false, "G": true, "H": true, "I": true, "J": true},
    "lake":      {"A": true, "B": true, "C": false, "D": true, "E": true, "F": true, "G": true, "H": true, "I": false, "J": true}
  }'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = '342f5d3e-c31b-4f49-9c84-7a0efdc5f99d';
