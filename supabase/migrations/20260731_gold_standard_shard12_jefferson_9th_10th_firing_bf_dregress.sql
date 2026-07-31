-- Gold Standard shard-12 jefferson -- 9th + 10th firing consolidated (2026-07-31, dispatch 675aa97f)
-- STATUS: 8/10 unchanged going in -- B/F remain BLOCKED (no viable lever). D regression FLAGGED
-- this firing (ghost-success, see below) -- live evaluator still reports D=PASS, but certification
-- readiness for D now correctly requires new evidence per ULTRALOOP protocol point 6.
--
-- CONTEXT: this dispatch (issue #17031) was independently worked twice in parallel:
--   1. claude[bot] GitHub Action auto-dispatch produced a 9th-firing diagnosis + migration but
--      left it STRANDED on branch claude/issue-17031-20260731-0801 (never merged to main) --
--      the exact "stranded branch" failure mode already identified once before in the 6th firing
--      (issue #12859: "shipped B/F auto-resolution parser was dead on main since 2026-07-20").
--      Per SHIP-TO-MAIN MANDATE (side branches score zero), this session merges that content in
--      rather than leaving it stranded again.
--   2. This interactive session ran an independent native ULTRALOOP 2-finder fan-out + a 4-letter
--      regression audit (C/D/E/I) via the Workflow tool, arriving at a CONVERGENT B/F conclusion
--      plus one new finding (D regression) the stranded branch did not check.
--
-- All 8 ultraloop_audit rows for this session were already inserted LIVE via the Supabase REST API
-- during this session (ids 11502-11509, dispatch_id=675aa97f-...). The INSERTs below are guarded
-- with NOT EXISTS so this migration is a safe no-op if applied against the same database (it will
-- not create duplicates), while still serving as the durable in-repo record of this firing.

-- ============================================================
-- B/F: unchanged, no viable lever (convergent finding, 2 independent investigations)
-- ============================================================
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'fallback',
    'jefferson',
    'B',
    '9th firing (claude[bot] auto-dispatch, merged from stranded branch claude/issue-17031-20260731-0801): B cannot move before 2026-08-19 -- case 25-CA-164 sold_amount unavailable from all public sources across 8 prior firings, 18+ sources exhausted. Auto-resolution wired via shard-jefferson-clerk-scraper.yml weekly cron.',
    '{"merged_from_branch": "claude/issue-17031-20260731-0801", "merged_commit": "f475a3c1003db6ced5b9b9b4472855251934df0c"}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'fallback',
    'jefferson',
    'F',
    '9th firing (merged from stranded branch): F cannot move before 2026-08-19, same root cause as B.',
    '{"merged_from_branch": "claude/issue-17031-20260731-0801"}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'B',
    '10th firing (this session, native ULTRALOOP 2-finder fan-out): re-confirmed B cannot move. 4 genuinely new angles checked beyond the 20+ already-exhausted list -- Jefferson County Tax Collector (live, distinct vendor, no deed/sale fields), Jefferson PA full ArcGIS org schema (no sale fields), archive.org Wayback (zero snapshots exist), FLCLERKS.com/2nd Circuit CMS (both resolve to same Turnstile gate). No sold_amount found or fabricated.',
    '{"verdict": "NOT_VIABLE", "convergent_with": "stranded-branch 9th firing"}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'F',
    '10th firing: F same root cause and fan-out as B this session.',
    '{}'::jsonb,
    true
  )
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
  SELECT 1 FROM gold_standard_ultraloop_audit a
  WHERE a.dispatch_id = v.dispatch_id AND a.county_slug = v.county_slug
    AND a.letter = v.letter AND a.ultraloop_mode = v.ultraloop_mode
    AND a.claim = v.claim
);

-- ============================================================
-- C/E/I regression audit: re-verified PASS-CONFIRMED-REAL this firing
-- ============================================================
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'C',
    'Regression audit: C=PASS (matched_clean=3) re-verified as genuinely real via independent cross-checks (live clerk PDF text extraction, DB row, FL GIO/DOR statewide cadastral) -- exact field matches on all 3, no PropertyOnion contamination.',
    '{"note": "parity_confidence/parity_checked_at/parity_divergences columns null on all 3 rows -- flagged as completeness gap, not disqualifying"}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'E',
    'Regression audit: E=PASS (parcel_linked=3) re-verified as genuinely real -- all 3 parcel_ids distinct, well-formed, independently cross-checked against live FL GIO cadastral (CO_NO=43) with matching owner/address.',
    '{"parcels_checked": 3}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'I',
    'Regression audit: I=PASS (card_complete=3 of 3) re-verified as genuinely real -- all 3 rows have real address/geo/value and parcel_id resolving to a real zone_code, denominator=numerator=3 exactly.',
    '{"rows_checked": 3}'::jsonb,
    true
  )
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
  SELECT 1 FROM gold_standard_ultraloop_audit a
  WHERE a.dispatch_id = v.dispatch_id AND a.county_slug = v.county_slug
    AND a.letter = v.letter AND a.ultraloop_mode = v.ultraloop_mode
    AND a.claim = v.claim
);

-- ============================================================
-- D: REGRESSION FOUND -- ghost-success flagged, NOT corrected here (see rationale)
-- ============================================================
-- D=PASS (matched_any=3) rests entirely on a static parity_source text-label convention applied
-- at scrape time, not on any real cross-source corroboration. po_listings has ZERO rows for
-- jefferson (no PropertyOnion litmus data exists for this county at all -- too small/rural to be
-- covered). parity_po_id/parity_confidence/parity_checked_at/tier1_verified_at are all NULL on
-- all 3 jefferson rows. Fleet-wide sanity check (run live this firing): of 19,127 rows with
-- parity_status='matched_clean', only 2,445 (12.8%) have a real parity_po_id link -- 87.2% pass
-- D by text-label convention alone. This is a SYSTEMIC evaluator-definition gap, not specific to
-- jefferson -- correcting it would mean either redefining the shared D predicate or bulk-auditing
-- fleet-wide parity data, both out of scope for a single-county shard session per PARALLEL-FLEET
-- RULES (do not touch shared code paths or other counties' data unilaterally). NOT fixed here.
-- Logging survived=false is sufficient to correctly gate certification: per ULTRALOOP protocol
-- point 6, jefferson's D reverts to UNKNOWN for cert purposes until a genuinely-survived row
-- post-dates this one, even though pencil_dod_evaluate_county() will keep returning pass=true
-- until the shared predicate or the underlying parity data is corrected by a session with the
-- proper fleet-wide scope.
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'D',
    'REGRESSION FOUND (ghost-success): D=PASS for jefferson rests on a static parity_source text-label convention with zero real po_listings corroboration (0 rows exist for jefferson). ~87.2% of fleet-wide matched_clean rows share this pattern -- systemic, not jefferson-specific. ESCALATED, not corrected this session (out of scope for single-county shard).',
    '{"po_listings_jefferson_count": 0, "fleet_wide_matched_clean_total": 19127, "fleet_wide_matched_clean_with_real_po_link": 2445, "fleet_wide_pct_ghost": 87.2, "recommendation": "ESCALATE to AI Architect / fleet dispatcher for D-criterion definition review or fleet-wide parity backfill"}'::jsonb,
    false
  )
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
  SELECT 1 FROM gold_standard_ultraloop_audit a
  WHERE a.dispatch_id = v.dispatch_id AND a.county_slug = v.county_slug
    AND a.letter = v.letter AND a.ultraloop_mode = v.ultraloop_mode
    AND a.claim = v.claim
);

-- ============================================================
-- SESSION CONCLUSION
-- ============================================================
-- jefferson: 8/10 live-evaluator unchanged (B/F genuinely blocked pending 2026-08-19 tax deed sale
-- or paid-API/manual-CAPTCHA escalation; D flagged as a ghost-success requiring architect review).
-- Next actionable window for B/F: 2026-08-24 (first Monday cron after 2026-08-19 sale).
-- RECOMMEND: fleet dispatcher suspend jefferson B/F re-fires until 2026-08-19 passes -- this is
-- the 10th consecutive dispatch with an identical B/F conclusion; further pre-08-19 re-fires
-- cannot move those two metrics and consume session budget for zero gain. D needs an
-- architect-level decision, not another county-scoped re-fire.
