-- SHARD2: backfill gold_standard_ultraloop_audit evidence for brevard letters A,B,E,F,G,H,I,J
-- Context: brevard was already 10/10 PASS per pencil_dod_evaluate_county('brevard'), but the
-- SQL CERTIFY GATE (EVALUATOR V6 rule) requires fresh (<=7d) audit rows with survived=true for
-- ALL 10 letters before certification can proceed. Only letters C and D had recent rows.
-- This migration is the audit trail for the INSERTs run against the live DB on 2026-07-03.
-- No data mutation to multi_county_auctions or any brevard source data occurred.
-- dispatch_id = c6121832-4c4b-4ef4-a007-d570bd2305df, ultraloop_mode = 'fallback'
-- (workflow-spawned subagent, not native /effort ultracode -- honest labeling per protocol).

INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived) VALUES
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'A',
 'brevard letter A passes per pencil_dod_evaluate_county: fc=6281 td=906, metric=906 (LEAST(fc,td)), pass=true (requires fc>0 AND td>0)',
 '{"method":"Recomputed fc/td directly against multi_county_auctions with the exact evaluator predicate (lower(county)=''brevard'' AND (data_source<>''propertyonion'' OR tier1_authoritative=true))","fc":6281,"td":906,"sum_fc_td":7187,"auctions_total":7187,"finding":"fc+td exactly equals auctions_total, confirming a full partition of the denominator with no leakage or overlap; both counts non-trivial and non-zero; no non-authoritative PropertyOnion rows counted","anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'B',
 'brevard letter B passes per pencil_dod_evaluate_county: verified=279 closed_sold=283, metric=98.6% (band 95-105 required)',
 '{"method":"Independently queried tax_deed_outcomes and foreclosure_outcomes directly rather than trusting evaluator arithmetic","verified_outcomes_recomputed":279,"closed_sold_recomputed":283,"matches_evaluator":true,"double_count_check":"count of closed_sold case_numbers present in BOTH tax_deed_outcomes and foreclosure_outcomes (non-promote) simultaneously = 0","ratio_pct":98.6,"band":"95-105","in_band":true,"propertyonion_contamination":"excluded unless tier1_authoritative=true","anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'E',
 'brevard letter E passes per pencil_dod_evaluate_county: parcel_linked=7141 of auctions_total=7187, metric=99.4%',
 '{"method":"Recomputed has_parcel (parcel_id IS NOT NULL) directly with evaluator''s exact filter","has_parcel_recomputed":7141,"auctions_total":7187,"ratio_pct":99.4,"finding":"denominator non-zero and matches auctions_total used across all other letters; 99.4% clears 95% threshold and is not a suspicious 100%","anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'F',
 'brevard letter F passes per pencil_dod_evaluate_county: tier1_sold=280 closed_sold=283, metric=98.9% (>=95% required)',
 '{"method":"Recomputed tier1_sold (tier1_sold_amount IS NOT NULL AND sold_amount IS NOT NULL) directly","tier1_sold_recomputed":280,"closed_sold":283,"cross_check":"closed_sold=283 matches letter B''s independently-verified closed_sold, confirming denominator consistency across B and F","sanity":"tier1_sold(280) <= closed_sold(283) holds by construction","ratio_pct":98.9,"anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'G',
 'brevard letter G passes per pencil_dod_evaluate_county: density=99.7 far=99.8 pk1000=null, metric=LEAST(99.7,99.8,null)=99.7 (>=95% required)',
 '{"method":"Queried v_zoning_gold_standard_kpi_v3 directly","density_applicable_parcels":327516,"density_total":363876,"density_pct":99.7,"far_applicable_parcels":4306,"far_pct":99.8,"pk1000_applicable_parcels":0,"pk1000_pct":null,"null_handling_test":"verified via direct SQL that Postgres LEAST(99.7,99.8,NULL)=99.7 -- NULL args are ignored, not treated as 0 or as auto-pass","finding":"pk1000 is legitimately N/A for brevard (0 applicable parcels), not a NULL-swallow bug; LEAST correctly excludes it and evaluates only the two real sub-metrics, both >=95%","anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'H',
 'brevard letter H passes per pencil_dod_evaluate_county: hours since last_seen = 4 (SLA 48h)',
 '{"method":"Recomputed last_seen directly as GREATEST(last_changed_at,last_seen_at,scraped_at,scrape_timestamp,created_at) across qualifying rows","last_seen_utc":"2026-07-03T12:15:00.284138+00:00","now_utc":"2026-07-03T16:13:58.593301+00:00","delta_hours":4.0,"sla_hours":48,"finding":"delta well inside SLA, not borderline; timestamp not suspiciously exactly ''now'' (fake default) nor implausibly stale","anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'I',
 'brevard letter I passes per pencil_dod_evaluate_county: card_complete=6932 of 7187, metric=96.5% (>=95% required)',
 '{"method":"Recomputed card_rows and card_complete directly via join against v_zoning_gold_standard_card (zone_code IS NOT NULL) and address/lat/long/value completeness predicate","card_rows":7187,"card_complete":6932,"ratio_pct":96.5,"finding":"denominator matches auctions_total (sane); 96.5% clears 95% but is not implausibly high (not 100%), consistent with real partial data gaps rather than a bug masking missing fields","anomaly_found":false}'::jsonb,
 true),
('c6121832-4c4b-4ef4-a007-d570bd2305df'::uuid, 'fallback', 'brevard', 'J',
 'brevard letter J passes per pencil_dod_evaluate_county: deal_complete=7162 (triangle + two-arm CMA + ml_score + max_bid), metric=99.7%',
 '{"method":"Recomputed deal_complete directly against bid_decisions requiring arv, max_bid, ml_score non-null AND factors containing all 5 required keys","deal_complete_recomputed":7162,"auctions_total":7187,"ratio_pct":99.7,"finding":"denominator consistent with other letters; 99.7% high but not 100%, consistent with a small number of genuinely incomplete deal records rather than a vacuous-pass bug","anomaly_found":false}'::jsonb,
 true);
