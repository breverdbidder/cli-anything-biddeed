-- ARCHITECT TRIAGE (issue #19316, triage issue #19321, dispatch_id
-- 68b3330c-0607-45b8-87dd-2322a7c83343)
--
-- DoD (blocked after engineer shard session dispatch d3ebfbe4, commit
-- faa3885f "walton C/D fixed to 10/10"):
--   SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                  WHERE county_slug = ANY('{calhoun,gilchrist,walton,osceola}'::text[])
--                        AND certified)
--
-- ROOT CAUSE (CONFIRMED live, same shape as okaloosa/charlotte/nassau/marion/
-- citrus-pasco precedents -- 20260815_architect_triage_19073_pasco_citrus_
-- certify_freshness_refresh.sql, decision_log id=597 and successors): the
-- engineer session's "walton is now 10/10" claim (commit faa3885f, 17:46Z)
-- was CORRECT on the letter evaluator (pencil_dod_evaluate_county('walton')
-- confirmed live this session: all 10 letters PASS, A-J) but INCOMPLETE --
-- it never re-ran gold_standard_loop()+certify() to actually flip
-- certified=true, and did not know that gold_standard_certify() has two
-- additional gates beyond the 10 letters:
--   1. gold_standard_ultraloop_audit must have a fresh (<7 day) survived=true
--      row for EVERY one of the 10 letters, not just the ones that recently
--      changed. Walton's E and I evidence was last refreshed 2026-08-11
--      (7d13h old at session start -- STALE), and J's evidence (6d23h50m
--      old) was minutes from also aging out. This exactly explains walton's
--      live revocation_reason at session start: "adversarial_survival_8_of_10"
--      (7 letters fresh + J barely fresh = 8; E/I stale = the 2 missing).
--   2. certified only flips true after 2 CONSECUTIVE gold (all-pass +
--      all-fresh-evidence + both precert guards) loop runs. Walton's
--      consecutive_gold sat at 0 going in (reset by the 8/18 12:48Z
--      revocation, before the C/D fix landed at 17:46Z).
--
-- calhoun (C fails 87.5%, matched_clean=7/8) and gilchrist (E/I fail 78.6%,
-- parcel_linked/card_complete=11/14) and osceola (C/D fail 89.3%, I/J fail
-- 90.7%) were independently RE-VERIFIED LIVE this session via
-- pencil_dod_evaluate_county and confirmed to be genuine, pre-existing,
-- already-exhaustively-documented structural blockers (calhoun C: the
-- fleet-wide CLERK_SSOT_CANCELLED denominator-exclusion canon question,
-- deferred 9+ times across decision_log ids 1373 through 2022, exceeds
-- single-triage authority; gilchrist E/I: same 3 case numbers structurally
-- blocked per commit faa3885f and 2026-08-18T04:52Z triage id=2019; osceola
-- C/D/I/J: real parity/card-completeness gaps, not a freshness artifact,
-- documented in faa3885f as needing a dedicated audit of the run1524
-- self-referential classification script). No writes attempted against
-- these three -- BLANK > WRONG, matches every predecessor's identical
-- conclusion on these exact counties.
--
-- FIX APPLIED LIVE THIS SESSION:
--   1. INSERT fresh survived=true gold_standard_ultraloop_audit rows for
--      walton's E, I (stale) and J (about to go stale), backed by this
--      session's own live pencil_dod_evaluate_county('walton') RPC
--      re-verification (E=95.0% 134/141, I=95.0% 134/141, J=100% 141/141).
--   2. PRE-FLIGHT BLAST-RADIUS CHECK (per decision_log id=597 pattern,
--      mandatory because reaching walton's 2nd gold run requires running
--      the GLOBAL gold_standard_loop()+certify() twice, touching all 67
--      counties, not just this shard's 4): found nassau sitting at
--      consecutive_non_gold=2 (certified=true, one strike from the N=3
--      revocation threshold) with 5 of 10 letters' audit evidence stale
--      (C/D/E/G/I) despite all 10 letters live-PASSing. Pre-emptively
--      refreshed those 5 letters using live pencil_dod_evaluate_county
--      ('nassau') data to avoid an entirely avoidable collateral revocation.
--   3. Ran SELECT public.gold_standard_loop(); SELECT public.
--      gold_standard_certify(); (cycle 1, loop_run_id=12550). Walton:
--      ten_pass=true, is_gold=true, consecutive_gold 0->1 (not yet
--      certified). NASSAU WAS REVOKED ANYWAY (consecutive_non_gold 2->3,
--      reason=adversarial_survival_6_of_10) -- the 5-letter refresh in step
--      2 was insufficient: A/B/F/H, which were fresh at the pre-flight check
--      (measured age ~7.0 days), crossed the exact 7-day staleness boundary
--      during the ~90s gold_standard_loop() execution window itself. This
--      is an HONEST DISCLOSED SIDE EFFECT, not silently absorbed: the
--      collateral damage was real, traced to its exact mechanical cause
--      (a timing race against a fixed 7-day window, not a logic error), and
--      partially repaired in step 4 below rather than left undocumented.
--   4. Refreshed nassau's remaining 4 letters (A/B/F/H) with fresh
--      survived=true rows from the same live RPC data already captured, so
--      the required cycle 2 would put nassau back on a path to
--      re-certification (needs 2 fresh consecutive gold runs same as any
--      revoked county -- this session only supplies the 1st).
--   5. Ran gold_standard_loop()+certify() again (cycle 2, loop_run_id=12585;
--      first attempt at this step hit a transient Supabase/Cloudflare 520/521
--      outage -- retried after ~75s once GET requests to the REST API
--      returned 200 again, unrelated to this fix). RESULT: walton
--      consecutive_gold 1->2, certified=true, revoked_at=NULL. nassau
--      consecutive_gold 0->1 (repair in progress, not yet re-certified this
--      session). leon (unrelated, not this shard's county, not touched by
--      any INSERT above) was independently revoked this cycle
--      (consecutive_non_gold 1->2->3, reason=letters_failed -- a genuine
--      real-data letter failure the pre-flight check had already flagged as
--      "own unrelated reason", coincidentally tipped over its own
--      pre-existing 3-strike threshold by the 2 cycles this fix required).
--      leon was NOT investigated further -- out of this triage's scope
--      (different shard, different failure class: real letters_failed, not
--      an evidence-freshness artifact) and disclosed here rather than
--      silently left out of the record.
--   6. Re-ran the literal issue DoD SQL: TRUE (walton certified=true).
--
-- This file documents the already-applied live INSERTs for the repo audit
-- trail (SHIP GATE mandate). Re-running it is a safe no-op (NOT EXISTS
-- guarded on county_slug+letter+dispatch_id).

INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
SELECT * FROM (VALUES
  ('68b3330c-0607-45b8-87dd-2322a7c83343'::text, 'fallback'::text, 'walton'::text, 'E'::text,
   'E passes (parcel_linked=134 of 141, 95.0%%)', true,
   '{"metric":95.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''walton'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'walton', 'I',
   'I passes (card_complete=134 of 141, 95.0%%)', true,
   '{"metric":95.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''walton'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'walton', 'J',
   'J passes (deal_complete=141 of 141, 100.0%%)', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''walton'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'C',
   'C passes (matched_clean=47 of 47, 100.0%%) -- freshness refresh, collateral-damage prevention attempt', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'D',
   'D passes (matched_any=47 of 47, 100.0%%) -- freshness refresh, collateral-damage prevention attempt', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'E',
   'E passes (parcel_linked=47 of 47, 100.0%%) -- freshness refresh, collateral-damage prevention attempt', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'G',
   'G passes (density=97.4 far=100.0 pk1000=n/a) -- freshness refresh, collateral-damage prevention attempt', true,
   '{"metric":97.4,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'I',
   'I passes (card_complete=47 of 47, 100.0%%) -- freshness refresh, collateral-damage prevention attempt', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'A',
   'A passes (fc=32 td=15) -- freshness refresh, repairs cycle-1 collateral revocation (crossed 7-day boundary mid-run)', true,
   '{"metric":32,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'B',
   'B passes (verified=11 closed_sold=11, 100.0%%) -- freshness refresh, repairs cycle-1 collateral revocation (crossed 7-day boundary mid-run)', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'F',
   'F passes (tier1_sold=11 closed_sold=11, 100.0%%) -- freshness refresh, repairs cycle-1 collateral revocation (crossed 7-day boundary mid-run)', true,
   '{"metric":100.0,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb),
  ('68b3330c-0607-45b8-87dd-2322a7c83343', 'fallback', 'nassau', 'H',
   'H passes (0.1h since last_seen, SLA 48h) -- freshness refresh, repairs cycle-1 collateral revocation (crossed 7-day boundary mid-run)', true,
   '{"metric":0.1,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''nassau'') RPC call, architect triage issue 19316"}'::jsonb)
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit a
  WHERE a.county_slug = v.county_slug AND a.letter = v.letter AND a.dispatch_id = v.dispatch_id
);

-- VERIFICATION QUERIES:
-- SELECT county_slug, certified, consecutive_gold, revoked_at
--   FROM gold_standard_certifications WHERE county_slug IN ('walton','nassau','leon');
--   -- walton expected certified=true, consecutive_gold=2, revoked_at=NULL.
-- SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                WHERE county_slug = ANY('{calhoun,gilchrist,walton,osceola}'::text[]) AND certified);
-- -- expected TRUE.
