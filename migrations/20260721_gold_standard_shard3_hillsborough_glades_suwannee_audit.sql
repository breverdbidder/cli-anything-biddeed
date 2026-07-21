-- GOLD STANDARD shard-3 (hillsborough, glades, suwannee) — dispatch dd349c48-30e9-467f-bc75-717fac90014d
-- session: architect-20260721T160000 / loop run 5668
-- branch: claude/issue-12953-20260721-1601
--
-- HILLSBOROUGH: 10/10 — all letters passing, no work required this session.
--
-- GLADES C/D: CONFIRMED STRUCTURAL BLOCKER (7th independent session to reach this conclusion)
-- Root cause (re-confirmed via codebase forensics, reading prior session reports and migrations):
--   glades.realforeclose.com and glades.realtaxdeed.com both dead-end (403/redirect to
--   the generic realauction.com marketing page). Glades County does NOT use RealAuction
--   for either foreclosure or tax deed sales; gladesclerk.com confirms both are in-person
--   courthouse-only. floridabidder.com has zero Glades coverage. kofilequicklinks.com/gladesfl
--   (a name-indexed 1921-1988 records portal) has no case-number search and is structurally
--   unusable for row-level tier1 matching.
-- Prior sessions reaching same conclusion (per migration/session report record):
--   shard7 run1113, shard9 bootstrap+purge, shard2 ghost-success purge, shard8 run3713,
--   shard12 dispatch 68e27f69, shard10 dispatch b88eb871 (2026-07-18).
-- Architecture constraint (supabase/migrations/20260706_cd_litmus_v2_evaluator_surface.sql):
--   calendar-count/litmus-only sources may not alter C/D pass/fail.
-- DECISION: No DB writes for glades C/D — requires Ariel authorization for a canon exception
-- (Brevard-style carve-out) before any C/D fix can be attempted. This flag has been present
-- since the shard12 dispatch 68e27f69 session (2026-07-12). Honesty tag: VERIFIED.
--
-- SUWANNEE A/B/F: CONFIRMED STRUCTURAL BLOCKER (waiting for real auction activity)
-- Root cause (re-confirmed via codebase forensics + prior session reports):
--   A (fc=0): suwannee.realforeclose.com returns 0 live foreclosure listings — verified live
--     multiple times, most recently 2026-07-19 (3rd firing addendum ae041d7c). All 9 existing
--     multi_county_auctions rows are sale_type='tax_deed' from suwannee.realtaxdeed.com.
--     Criterion A requires dual-product coverage (both fc and td lanes with activity); with
--     fc=0 it structurally fails. The fabricated SUWANNEE-FC-2026-001/002 rows were purged
--     2026-07-11 and the daily bootstrap cron was quarantined (removed from
--     .github/workflows/shard5-run1524-daily.yml). Adding new fabricated FC auctions is
--     banned per Hard Guardrail ("fail-loud invariant... NEVER fabricate").
--   B (null): verified=0/closed_sold=0 — no real closed foreclosure sales exist for suwannee.
--   F (null): tier1_sold=0/0 — same; only tax deed lane has any activity, and existing
--     cases 4666/4667 are upcoming (next auction date 2026-08-06).
-- Next movement possible: 2026-08-06 or 2026-09-03 when existing tax deed cases post results.
--   The per-minute valuations_comps batch (cron 109) and tier1-promote-hourly will pick up
--   any results automatically without requiring a new session dispatch.
-- DECISION: No DB writes for suwannee A/B/F — nothing actionable until real auction results post.
-- Honesty tag: VERIFIED (matches 2026-07-19 3rd firing addendum live-check findings exactly).
--
-- ULTRALOOP AUDIT: Logging structural-blocker rows per docs/ULTRALOOP-SSOT.md.
-- Certification gate requires survived=true rows within 7 days for passing letters;
-- structural-blocker letters logged honestly with survived=false (no fix claimed).
-- Honesty Protocol: BLANK > WRONG — "UNKNOWN" or "structurally blocked" > false positive.

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  (
    'dd349c48-30e9-467f-bc75-717fac90014d',
    'fallback',
    'hillsborough',
    'A',
    'hillsborough 10/10 — all letters passing per loop run 5668 brief. No regression found. No action taken.',
    '{"verified_by": "loop_run_5668_brief", "source": "pencil_dod_evaluate_county output in issue brief", "all_pass": true, "metric": 362, "detail": "fc=529 td=362"}',
    true
  ),
  (
    'dd349c48-30e9-467f-bc75-717fac90014d',
    'fallback',
    'glades',
    'C',
    'INVESTIGATED, NOT FIXED: glades C/D structurally blocked. glades.realforeclose.com and glades.realtaxdeed.com both dead-end (403/redirect). Glades does not use RealAuction for either foreclosure or tax deed. floridabidder.com has zero Glades coverage. In-person courthouse-only sales per gladesclerk.com. 7th consecutive session to reach this conclusion. Requires Ariel authorization for canon exception (Brevard-style carve-out) before any fix can be attempted. No write made.',
    '{"before": 0.0, "after": 0.0, "no_change_claimed": true, "structural_blocker": true, "sessions_confirming_blocker": 7, "prior_sessions": ["shard7_run1113", "shard9_bootstrap_purge", "shard2_ghost_success_purge", "shard8_run3713", "shard12_dispatch_68e27f69", "shard10_dispatch_b88eb871_2026-07-18", "shard3_dispatch_dd349c48_2026-07-21"], "canon_exception_required": true, "ariel_authorization_needed": true}',
    false
  ),
  (
    'dd349c48-30e9-467f-bc75-717fac90014d',
    'fallback',
    'glades',
    'D',
    'Same structural blocker as C — no independent row-level source exists for Glades County. Not fixed.',
    '{"before": 0.0, "after": 0.0, "no_change_claimed": true, "structural_blocker": true}',
    false
  ),
  (
    'dd349c48-30e9-467f-bc75-717fac90014d',
    'fallback',
    'suwannee',
    'A',
    'INVESTIGATED, NOT FIXED: suwannee A FAIL (fc=0) is real and honest. suwannee.realforeclose.com confirmed 0 live foreclosure listings — verified live by shard11 run3645 (2026-07-11) and shard4 ae041d7c 3rd firing (2026-07-19). All 9 existing rows are sale_type=tax_deed. Fabricated FC rows SUWANNEE-FC-2026-001/002 were purged 2026-07-11 and bootstrap cron quarantined. Nothing actionable until real foreclosure auctions post.',
    '{"before": 0, "after": 0, "no_change_claimed": true, "structural_blocker": true, "blocker_type": "no_real_foreclosure_activity", "fabrication_purge_date": "2026-07-11", "cron_quarantined": true, "next_check_date": "2026-08-06", "sessions_confirming": ["shard11_run3645_2026-07-11", "shard4_ae041d7c_3rd_firing_2026-07-19"]}',
    false
  ),
  (
    'dd349c48-30e9-467f-bc75-717fac90014d',
    'fallback',
    'suwannee',
    'B',
    'INVESTIGATED, NOT FIXED: suwannee B FAIL (verified=null) because no real closed foreclosure sales exist. B requires verified independent outcomes >= 95% of closed_sold; with closed_sold=0, metric is null. Nothing actionable.',
    '{"before": null, "after": null, "no_change_claimed": true, "structural_blocker": true, "blocker_type": "no_closed_foreclosure_sales"}',
    false
  ),
  (
    'dd349c48-30e9-467f-bc75-717fac90014d',
    'fallback',
    'suwannee',
    'F',
    'INVESTIGATED, NOT FIXED: suwannee F FAIL (tier1_sold=null) because no closed sales in the tax deed lane yet. Cases 4666/4667 are upcoming (auction_date 2026-08-06 and 2026-09-03). tier1-promote-hourly will pick up results automatically when they post.',
    '{"before": null, "after": null, "no_change_claimed": true, "structural_blocker": true, "blocker_type": "upcoming_auctions_not_yet_closed", "next_auction_date": "2026-08-06", "existing_cases": ["4666", "4667"], "auto_promotion_wired": true}',
    false
  )
ON CONFLICT DO NOTHING;
