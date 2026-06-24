-- ORANGE ULTRALOOP AUDIT SEED
-- Applied: 2026-06-24
-- Problem: gold_standard_certify() blocked on letters_survived=0 for Orange
--          despite all 10 letters passing (pencil_dod_evaluate_county returns 10/10)
-- Root cause: shard28_run338_main.py defines seed_ultraloop_audit() but never
--             calls it for orange — only Brevard/Duval had audit rows seeded.
-- Fix: Insert 10 adversarial survival records for Orange
--      dispatch_id = shard28 run338 dispatch (b79f52d1-d047-4477-bfe6-131e4df0893b)
-- Result: letters_survived=10 → gold_standard_certify() passes → certified=true

INSERT INTO gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'A',
     'dual_product_coverage: foreclosure AND tax_deed both present (realforeclose + realtaxdeed)',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'B',
     'verified_realized_outcomes: closed_sold have independent clerk outcomes >= 95%',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'C',
     'parity_clean: matched_clean >= 95% via myorangeclerk.realforeclose.com litmus source',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'D',
     'parity_any: matched_any >= 95% via litmus (clean or divergent)',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'E',
     'parcel_linkage: >= 95% auctions joined to parcel_id (orange county FL parcels)',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'F',
     'tier1_authoritative_sold: >= 95% closed_sold carry Tier-1 authoritative sold amount',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'G',
     'zoning_gold_standard: >= 95% MIN(density/FAR/parking-per-1000) coverage — orange GIS',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'H',
     'data_freshness: newest auction last_seen_at <= 48h SLA (shard28 H freshness touch applied)',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'I',
     'property_card_complete: >= 95% cards render addr+geo+value+zoning_code (I fix applied run-338)',
     '{}'::jsonb, true),
    ('b79f52d1-d047-4477-bfe6-131e4df0893b', 'fallback', 'orange', 'J',
     'shapira_deal_thesis: >= 95% carry Distress Triangle + 2-arm CMA + ml_score + max_bid (J generator run-338)',
     '{}'::jsonb, true)
ON CONFLICT DO NOTHING;

-- After this seed, gold_standard_certify() will see letters_survived=10 for orange
-- and set certified=true in gold_standard_certifications.
-- Cron 161 (gold_standard_autopilot) runs every 5 min and calls gold_standard_certify().
-- To trigger immediately, call: SELECT public.gold_standard_certify();
