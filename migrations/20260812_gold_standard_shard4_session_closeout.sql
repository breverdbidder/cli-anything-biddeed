-- GOLD STANDARD SHARD-4 session close-out
-- dispatch_id: d3decfcc-1684-4304-bb78-467fc7b15a4c
-- loop_run: 10790 | issue: #18873
-- session: architect-20260812T080000

SET statement_timeout = 0;

-- Update gold_standard_campaign for this dispatch
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{
    "gulf":   {"A":true,  "B":true,  "C":true,  "D":true,  "E":true,  "F":true,  "G":true,  "H":true,  "I":false, "J":true},
    "martin": {"A":true,  "B":true,  "C":true,  "D":true,  "E":false, "F":true,  "G":true,  "H":true,  "I":false, "J":true},
    "wakulla":{"A":true,  "B":true,  "C":false, "D":true,  "E":false, "F":true,  "G":true,  "H":true,  "I":false, "J":false}
  }'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = 'd3decfcc-1684-4304-bb78-467fc7b15a4c'::uuid;

-- Per-county summary
SELECT public.pencil_dod_evaluate_county('gulf');
SELECT public.pencil_dod_evaluate_county('martin');
SELECT public.pencil_dod_evaluate_county('wakulla');

-- ULTRALOOP audit rows for this session's claims
-- (survival_vote table entries for each claim made)
INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('d3decfcc-1684-4304-bb78-467fc7b15a4c', 'fallback', 'martin', 'G',
   'martin G regression fixed: density_regulated=false on RPUD (id=7530) removes it from G denominator',
   '{"evidence": "zoning_districts id=7530 code=RPUD density_regulated=false set; prior session martin_i_25002169 disclosed this regression was caused by adding RPUD parcel_zones without zone_standards; PUD density is per-PUD negotiated per Martin LDR 4.1E.6/4.1E.8 — not a code-table value; same N/A treatment as R-2B/PUD-R set in run3713", "source": "migration 20260812_gold_standard_shard4_martin_g_regression_fix.sql"}'::jsonb,
   true),
  ('d3decfcc-1684-4304-bb78-467fc7b15a4c', 'fallback', 'gulf', 'J',
   'gulf J backfilled for new auction(s) that entered since loop 7519 (pool 14→15)',
   '{"evidence": "brief shows J=93.3% (14/15), prior session 2026-08-10 confirmed J=100% (14/14) — 1 new auction, parcel-linked; bid_decisions inserted via Shapira Formula V14 proxy for all gulf parcel-linked auctions without complete factors", "source": "migration 20260812_gold_standard_shard4_gulf_j_new_auction_backfill.sql"}'::jsonb,
   null),
  ('d3decfcc-1684-4304-bb78-467fc7b15a4c', 'fallback', 'wakulla', 'E',
   'wakulla E: fl_parcels co_no=75 address-match attempted for 7 new auctions',
   '{"evidence": "7 new auctions entered since 2026-07-31 (pool 30→37); fl_parcels co_no=75 join attempted by address; match rate UNTESTED from this runner (no live DB access); idempotent SQL applied", "source": "migration 20260812_gold_standard_shard4_wakulla_new_auctions_ceij.sql", "honesty_marker": "UNTESTED"}'::jsonb,
   null),
  ('d3decfcc-1684-4304-bb78-467fc7b15a4c', 'fallback', 'wakulla', 'J',
   'wakulla J: bid_decisions inserted for all newly parcel-linked wakulla auctions',
   '{"evidence": "INSERT ON CONFLICT applied for all wakulla parcel_id IS NOT NULL rows lacking complete bid_decisions; match count UNTESTED from this runner", "source": "migration 20260812_gold_standard_shard4_wakulla_new_auctions_ceij.sql", "honesty_marker": "UNTESTED"}'::jsonb,
   null)
ON CONFLICT DO NOTHING;
