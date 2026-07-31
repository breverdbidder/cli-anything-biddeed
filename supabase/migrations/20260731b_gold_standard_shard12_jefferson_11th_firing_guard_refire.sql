-- Gold Standard shard-12 jefferson -- 11th firing (2026-07-31, dispatch 675aa97f, issue #17031
-- GUARD RE-FIRE attempt 2/3). Same dispatch_id as the 9th+10th firing migration
-- (20260731_gold_standard_shard12_jefferson_9th_10th_firing_bf_dregress.sql, commit 993705e2/b2e44a38,
-- already on main). This is a DUPLICATE re-dispatch of an already-fully-worked issue -- the automated
-- guard re-fires until 10/10 or an explicit blocker comment lands. jefferson cannot reach 10/10 before
-- the 2026-08-19 tax deed sale (B/F) and D requires a fleet-wide evaluator decision outside this shard's
-- authority (out of scope per PARALLEL-FLEET RULES).
--
-- STATUS: 8/10 unchanged (A,C,D,E,G,H,I,J live-evaluator PASS; B,F FAIL). No metric moved.
--
-- WHAT THIS FIRING DID (ultracode Workflow-tool 2-finder + 2-refuter adversarial fan-out, in addition
-- to a fresh live pencil_dod_evaluate_county() + ultraloop_audit + GHA-cron-health re-check that found
-- zero drift from the 10th firing):
--   - Confirmed live state matches the 10th firing exactly: 2 tax-deed sales (26-TD-04, 26-TD-05) still
--     scheduled 2026-08-19 (future), foreclosure 25-CA-164 sold 2026-06-25 with sold_amount still NULL.
--   - shard-jefferson-clerk-scraper.yml cron confirmed healthy (last success 2026-07-27, weekly Monday).
--   - Finder checked 3 fresh angles + 1 genuinely new independent source (floridaparcels.com) for
--     case 25-CA-164's sold amount -- all negative, no fabrication.
--   - A refuter flagged myfloridacounty.com/orisearch/33 as a supposedly-unexploited lead; cross-checked
--     against this dispatch's own 2nd/3rd firing addenda (already on main) and confirmed that URL has
--     been Turnstile-blocked and exhausted via Playwright form-submission attempts since the 2nd firing.
--     The refuter's dismissal was a false positive from incomplete context, not a genuine new lever.
--   - D ghost-success finding (from the 10th firing) independently re-confirmed and strengthened:
--     PropertyOnion's own FL coverage directory lists 48/67 counties; Jefferson is absent and its
--     per-county coverage URL 404s. This is a structural source-coverage gap, not a scraper bug.
--     Recommend jeffersonclerk.com as an alternate litmus for D specific to jefferson, but redefining
--     the shared D predicate is a fleet-wide decision outside this single-county shard's scope.
--
-- 3 new gold_standard_ultraloop_audit rows already inserted LIVE via Supabase REST this session
-- (ids 11694 B survived=true, 11695 F survived=true, 11696 D survived=false). INSERTs below are
-- guarded with NOT EXISTS so this migration is a safe no-op if applied against the same database.

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'B',
    '11th firing (this session, GUARD RE-FIRE attempt 2/3 on the same dispatch/issue #17031): ultracode 2-finder + 2-refuter adversarial pass. Finder checked 3 fresh angles (Landmark Web/GovOS portal -- does not exist for this county, only for Jefferson County AL; Circuit Civil docket separate from OCRS -- does not exist publicly; local news/legal-notice archive search -- no search capability) plus one genuinely new independent source, floridaparcels.com, which has a live page for the exact parcel (340 S Marvin St) but shows only a 2014 entry and owner-of-record still James Thompson -- deed transfer has not propagated there. Refuter flagged myfloridacounty.com/orisearch/33 as a supposedly-unexploited lead; cross-checked against this dispatch''s own prior-firing addenda (2nd and 3rd firing, committed to main) and confirmed that URL has been tried and Turnstile-blocked since the 2nd firing via Playwright form-submission attempts -- refuter lacked that history, false-positive dismissed. No sold_amount found or fabricated. Case 25-CA-164 remains genuinely blocked pending the clerk''s post-sale publication.',
    '{"refuter_flagged_lever": "myfloridacounty.com/orisearch/33", "verdict": "false_positive -- already exhausted since 2nd firing via Playwright, not a new lever", "new_source_floridaparcels_com": "live, independent, non-PropertyOnion, confirmed no 2026 sale data present"}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'F',
    '11th firing: F same root cause and same fan-out as B this session (closed_sold count for tier1 verification is driven by the same case 25-CA-164 blocker). No new lever found.',
    '{}'::jsonb,
    true
  ),
  (
    '675aa97f-3855-4c8c-b5e8-3ae2afc96d6d'::uuid,
    'native',
    'jefferson',
    'D',
    '11th firing: strengthened confirmation of the 10th-firing ghost-success finding. Independently fetched PropertyOnion''s own FL coverage directory (propertyonion.com/coverage/Florida): exact list extracted, 48 of 67 FL counties covered, Jefferson absent. propertyonion.com/coverage/Florida/Jefferson returns HTTP 404 (contrast: real county pages resolve). Refuter independently reproduced all three checks (48-county list, 404, SEO-stub-only guessed URL) and found no contradicting evidence. Jefferson is structurally outside PropertyOnion''s footprint -- this is a source-coverage gap, not a scraper bug, and cannot be fixed by rescraping. Recommend jeffersonclerk.com as an alternate county-authoritative litmus source for D specific to Jefferson, but redefining the shared D predicate (or which counties use which litmus) is a fleet-wide evaluator decision outside this single-county shard''s authority per PARALLEL-FLEET RULES -- escalating again, not unilaterally correcting.',
    '{"po_fl_coverage_count": "48/67", "po_jefferson_page_status": 404, "refuter_verdict": "claim survives, independently reproduced", "alternate_litmus_recommended": "jeffersonclerk.com/services/public-sales/"}'::jsonb,
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
-- SESSION CONCLUSION (11th firing)
-- ============================================================
-- jefferson: 8/10 live-evaluator unchanged. B/F genuinely blocked until the 2026-08-19 tax deed sale
-- clears and the clerk's weekly cron (shard-jefferson-clerk-scraper.yml, confirmed healthy) picks up
-- the results -- next productive window 2026-08-24. D remains an open architect-level decision
-- (fleet-wide D predicate / litmus-source redefinition), not a single-county fix.
-- RECOMMEND (repeated from 10th firing, now with an 11th confirming data point): fleet dispatcher
-- suspend jefferson B/F re-fires until 2026-08-19 passes. This is the 11th consecutive dispatch on
-- this issue/county pair with an identical B/F conclusion.
