-- Gold Standard shard-1 (duval, union) — dispatch 3aafe92d-0524-49ec-a81e-4ea3627def8b
-- loop run 6871 · chat_session architect-20260727T160000 · 2026-07-27
--
-- Scope: AUDIT-ONLY. No county-status or outcome writes.
--
-- DUVAL (10/10): All 10 criteria pass per run 6871 brief. This session re-confirmed
-- zero drift vs prior verified state. No action taken.
--
-- UNION (8/10): B=null, F=null. Structural block confirmed for the 5th consecutive
-- session by cross-referencing the run 6871 brief against the 4th firing report
-- (dispatch 1a211136, 2026-07-20) and run 6046 shard-3 report (2026-07-23):
--   * UNION-TD-CERT223: status unknown_past_due/redeemed — never went to auction
--   * 63-2025-CA-0053: upcoming, auction_date 2026-08-13 (17 days from session date)
--   * 63-2024-CA-0047: upcoming, auction_date 2026-10-15
-- closed_sold=0 is correct, not a bug. B and F are mathematically impossible until
-- at least one auction closes. Do NOT re-investigate or attempt workarounds before
-- 2026-08-13. The CAMPAIGN'S OWN GUIDANCE applies: switch to the next county/letter
-- rather than idling — but union has no other failing letters to work.
--
-- Per PARALLEL-FLEET RULES: gold_standard_loop()/certify() not run from this session.
-- Per-county pencil_dod_evaluate_county is the verification mechanism.

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  (
    '3aafe92d-0524-49ec-a81e-4ea3627def8b',
    'fallback',
    'duval',
    'ALL',
    'VERIFIED: duval 10/10 confirmed at run 6871. All criteria (A=77, B=100.0, C=99.3, D=99.5, E=100.0, F=98.2, G=100.0, H=0.1, I=98.8, J=100.0) pass per loop run 6871 brief. Cross-checked against prior session history — no regression found. Zero drift. No writes required.',
    jsonb_build_object(
      'source', 'run_6871_brief_issued_20260727T160000Z',
      'prior_sessions', 'shard-11 dispatch 1a211136 (2026-07-19/20), shard-3 run 6046 (2026-07-23) — consistent with 10/10',
      'honesty_marker', 'VERIFIED — run 6871 brief is the authoritative source for this session; independent live DB query not executable from GHA runner without credentials',
      'no_writes', true
    ),
    true
  ),
  (
    '3aafe92d-0524-49ec-a81e-4ea3627def8b',
    'fallback',
    'union',
    'B',
    'VERIFIED STRUCTURAL BLOCK: union B=null (closed_sold=0) is correct and cannot be remediated before 2026-08-13. All 3 union auctions verified: UNION-TD-CERT223 (redeemed/past_due, never went to sale), 63-2025-CA-0053 (upcoming 2026-08-13), 63-2024-CA-0047 (upcoming 2026-10-15). B requires pct_verified_outcomes >= 95% from INDEPENDENT data_source — mathematically impossible with closed_sold=0. No independent source exists for zero closed auctions. Consistent with shard-11 dispatch 1a211136 firings 1-4 (2026-07-19 and 2026-07-20) and shard-3 run 6046 (2026-07-23).',
    jsonb_build_object(
      'source', 'run_6871_brief_20260727 + shard11_4th_firing_report_20260720 + shard3_run6046_session_report_20260723',
      'auction_inventory', jsonb_build_array(
        jsonb_build_object('case_number', 'UNION-TD-CERT223', 'status', 'unknown_past_due/redeemed', 'sale_date', '2026-03-12', 'went_to_auction', false),
        jsonb_build_object('case_number', '63-2025-CA-0053', 'status', 'upcoming', 'auction_date', '2026-08-13'),
        jsonb_build_object('case_number', '63-2024-CA-0047', 'status', 'upcoming', 'auction_date', '2026-10-15')
      ),
      'earliest_possible_close', '2026-08-13',
      'honesty_marker', 'VERIFIED — per HONESTY PROTOCOL: BLANK > WRONG. closed_sold=0 is factually correct, not a gap to fill.',
      'refuted', false
    ),
    true
  ),
  (
    '3aafe92d-0524-49ec-a81e-4ea3627def8b',
    'fallback',
    'union',
    'F',
    'VERIFIED STRUCTURAL BLOCK: union F=null (tier1_sold=0, closed_sold=0) is correct. F requires pct_tier1_sold >= 95% of closed auctions — same root cause as B (zero closed auctions). No tier1 sold amount can exist until at least one auction closes. Earliest possible date: 2026-08-13. No writes to foreclosure_outcomes or tax_deed_outcomes for union. Consistent with all 4 prior shard-11 firings.',
    jsonb_build_object(
      'source', 'run_6871_brief_20260727 + shard11_4th_firing_report_20260720 + shard3_run6046_session_report_20260723',
      'earliest_possible_close', '2026-08-13',
      'honesty_marker', 'VERIFIED — per HONESTY PROTOCOL: BLANK > WRONG. tier1_sold=0 is factually correct.',
      'refuted', false
    ),
    true
  );
