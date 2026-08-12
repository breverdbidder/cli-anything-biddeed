-- SHARD-3 SESSION CLOSEOUT (dispatch b57474e3)
-- loop_run: 10790 | issue: #18871
-- session: architect-20260812T080000
--
-- Logs ultraloop_audit rows (fallback mode — manual fan-out in restricted runner)
-- and updates gold_standard_campaign closeout fields.
--
-- HONESTY PROTOCOL tags:
--   All letter claims here are UNTESTED until the E/J migration runs live.
--   These rows record the INTENDED work, not verified outcomes.
--   After the migration runs: re-run pencil_dod_evaluate_county per county
--   and update survived/refuter_evidence based on actual metrics.

SET statement_timeout = 0;

-- ─────────────────────────────────────────────────────────────────
-- 1. Ultraloop audit rows (one per letter per county worked)
--    survived = NULL until migration verified live
--    honesty_marker = 'UNTESTED' per Honesty Protocol
-- ─────────────────────────────────────────────────────────────────

INSERT INTO gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
-- ALACHUA
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'alachua', 'E',
 'Address-match via fl_parcels co_no=11 on new rows without parcel_id (73 total, need 70/73=95.9% to pass)',
 '{"honesty_marker":"UNTESTED","method":"fl_parcels address match","co_no":11,"blocked_cases":["01 2025 CA 001928","01 2025 CA 002643","01 2025 CA 003919","01 2025 CA 003287"],"note":"4 confirmed-blocked cases from prior sessions; migration is idempotent"}',
 NULL, NOW()),
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'alachua', 'J',
 'Shapira Formula v14 bid_decisions for parcel-linked alachua rows (ml_score=0.52 INFERRED)',
 '{"honesty_marker":"UNTESTED","method":"INSERT INTO bid_decisions WHERE parcel_id IS NOT NULL AND complete_bd NOT EXISTS","ml_score_marker":"INFERRED","note":"J blocked by same 4-row E gap; only rows with parcel_id get bid_decisions"}',
 NULL, NOW()),

-- GADSDEN
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'gadsden', 'E',
 'Address-match via fl_parcels co_no=30 for 40 new gadsden rows (63 total, need 60/63=95.2%)',
 '{"honesty_marker":"UNTESTED","method":"fl_parcels address match","co_no":30,"blocked_cases":["25000901CA","25000942CA"],"blocked_reason":"metes-and-bounds address / manufactured home — confirmed 5+ sessions"}',
 NULL, NOW()),
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'gadsden', 'C',
 'Promote parity_status=PARITY_OK for newly parcel-linked gadsden rows with null parity_status (8 CLERK_SSOT_CANCELLED excluded)',
 '{"honesty_marker":"UNTESTED","method":"UPDATE WHERE parcel_id IS NOT NULL AND parity_status IS NULL AND != CLERK_SSOT_CANCELLED","note":"C structurally capped at 55/63=87.3% by 8 cancelled TD sales — CLERK_SSOT_CANCELLED cannot be promoted to PARITY_OK without fabrication"}',
 NULL, NOW()),
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'gadsden', 'J',
 'Shapira Formula v14 bid_decisions for parcel-linked gadsden rows (ml_score=0.42 INFERRED — matches prior session)',
 '{"honesty_marker":"UNTESTED","method":"INSERT INTO bid_decisions WHERE parcel_id IS NOT NULL AND complete_bd NOT EXISTS","ml_score_marker":"INFERRED","prior_session":"20260811 cefc3fb1 gadsden J INSERT already shipped for 59 rows; this covers the gap rows from 40 new ingested"}',
 NULL, NOW()),

-- SUMTER
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'sumter', 'E',
 'Address-match via fl_parcels co_no=70 for new sumter rows (21 total, need 20/21=95.2%)',
 '{"honesty_marker":"UNTESTED","method":"fl_parcels address match","co_no":70,"blocked_cases":["2025-CA-000255"],"blocked_reason":"Cloudflare-gated on all 3 PA sources — 4th session confirming same wall; do not retry via plain HTTP"}',
 NULL, NOW()),
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'sumter', 'J',
 'Shapira Formula v14 bid_decisions for parcel-linked sumter rows (ml_score=0.55 INFERRED — The Villages high-demand)',
 '{"honesty_marker":"UNTESTED","method":"INSERT INTO bid_decisions WHERE parcel_id IS NOT NULL AND complete_bd NOT EXISTS","ml_score_marker":"INFERRED","note":"Prior 15799 migration purged ghost bid_decisions; new rows from 10 newly-ingested auctions need fresh inserts for those with parcel_id"}',
 NULL, NOW()),

-- HOLMES
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'holmes', 'E',
 'Address-match via fl_parcels co_no=40 for 4 new holmes rows (17 total, need 17/17=100% or 16/17=94.1% at minimum)',
 '{"honesty_marker":"UNTESTED","method":"fl_parcels address match","co_no":40,"note":"Prior sessions confirmed E=100% for 13 rows; 4 new rows from recent ingest may have addresses from holmesclerk.com scrape"}',
 NULL, NOW()),
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'holmes', 'C',
 'Promote parity_status=PARITY_OK for newly parcel-linked holmes rows from source_platform=holmes_clerk',
 '{"honesty_marker":"UNTESTED","method":"UPDATE WHERE parcel_id IS NOT NULL AND parity_status IS NULL AND source_platform=holmes_clerk","note":"Holmes uses holmesclerk.com self-referential litmus (tier1 source); PropertyOnion not in play"}',
 NULL, NOW()),
('b57474e3-1a2a-4938-bb03-a5e57905841e', 'fallback', 'holmes', 'J',
 'Shapira Formula v14 bid_decisions for parcel-linked holmes rows (ml_score=0.38 INFERRED — rural panhandle)',
 '{"honesty_marker":"UNTESTED","method":"INSERT INTO bid_decisions WHERE parcel_id IS NOT NULL AND complete_bd NOT EXISTS","ml_score_marker":"INFERRED"}',
 NULL, NOW())

ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────────
-- 2. Session closeout on gold_standard_campaign
-- ─────────────────────────────────────────────────────────────────

UPDATE public.gold_standard_campaign
SET
    criteria_passed = jsonb_build_object(
        'alachua', jsonb_build_object('A',true,'B',true,'C',true,'D',true,'E',false,'F',true,'G',true,'H',true,'I',false,'J',false),
        'gadsden', jsonb_build_object('A',true,'B',true,'C',false,'D',true,'E',false,'F',true,'G',true,'H',true,'I',false,'J',true),
        'sumter',  jsonb_build_object('A',true,'B',true,'C',true, 'D',true,'E',false,'F',true,'G',true,'H',true,'I',false,'J',false),
        'holmes',  jsonb_build_object('A',true,'B',false,'C',false,'D',false,'E',false,'F',false,'G',true,'H',true,'I',false,'J',false)
    ),
    criteria_total = 10,
    exit_reason = 'timeout',
    session_end_at = NOW()
WHERE dispatch_id = 'b57474e3-1a2a-4938-bb03-a5e57905841e';

-- ─────────────────────────────────────────────────────────────────
-- 3. Post-migration verification (run AFTER E/J migration applied)
-- ─────────────────────────────────────────────────────────────────

SELECT public.pencil_dod_evaluate_county('alachua');
SELECT public.pencil_dod_evaluate_county('gadsden');
SELECT public.pencil_dod_evaluate_county('sumter');
SELECT public.pencil_dod_evaluate_county('holmes');
