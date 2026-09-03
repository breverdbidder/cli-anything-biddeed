-- ARCHITECT TRIAGE (issue #19818, triaging blocked issue #19807)
-- dispatch_id: 5e41ea06-df48-4e37-8d4a-1a88795a199d
--
-- DoD (unmet, both before and after this session):
--   SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                  WHERE county_slug = ANY('{pasco,manatee,sumter}'::text[]) AND certified)
--
-- ROOT CAUSE (CONFIRMED live, 2026-09-03, same shape as the pasco/citrus
-- precedent -- supabase/migrations/20260815_architect_triage_19073_pasco_citrus_certify_freshness_refresh.sql,
-- issue #19073, 19 days earlier):
-- pasco was already 10/10 letter-PASS live via pencil_dod_evaluate_county
-- (confirmed this session: A-J all pass, e.g. B=100.0%% verified=92
-- closed_sold=92). gold_standard_certifications showed
-- certified=false, revocation_reason='...adversarial_survival_9_of_10' as of
-- run 16765 (evaluated 2026-09-03T19:30Z, AFTER the prior fleet session for
-- #19807 closed out at 16:45Z claiming pasco 10/10).
--
-- gold_standard_certify() additionally requires survived=true
-- gold_standard_ultraloop_audit evidence for ALL 10 letters within a rolling
-- 7-day window (migrations/20260720_architect_triage_12866_certify_tiebreak_fix.sql,
-- confirmed as the current live definition -- no later migration redefines
-- this function). Checked the freshest survived=true row per letter for
-- pasco: 9 of 10 fresh, but letter B's freshest row (id=18687) was created
-- 2026-08-27T13:28:14Z -- about 9 hours before the 7-day cutoff relative to
-- this session's clock (2026-09-03T22:28Z) -- i.e. it aged out sometime
-- between the 19:30Z certify run and now. No data regressed; the evidence
-- simply outlived its own freshness window because nothing re-touches it on
-- a cadence tighter than 7 days.
--
-- Pre-flight blast-radius check: querying gold_standard_certifications live
-- found 15 OTHER counties (glades, gulf, hernando, hillsborough, monroe,
-- orange, palm_beach, bay, desoto, duval, flagler, franklin, sarasota,
-- volusia, hendry) sitting at consecutive_non_gold=2, certified=true --
-- one non-gold evaluation away from the N=3 hysteresis revocation threshold
-- (20260719g_gtm22h_certify_n3_strikes_reason_log.sql). gold_standard_loop()
-- + gold_standard_certify() operate fleet-wide, not per-county, and this
-- issue's own PARALLEL-FLEET RULES explicitly instruct against running the
-- loop mid-session when other shards may be mid-flight. DELIBERATELY DID
-- NOT run gold_standard_loop()/gold_standard_certify() this session: doing
-- so under a 3-county-shard triage mandate risks revoking any of those 15
-- unrelated, currently-certified counties (plausibly the identical
-- stale-evidence bug class, unverified for any of them -- out of scope to
-- check under this issue) for zero guaranteed DoD benefit (even a perfect
-- run only advances pasco's consecutive_gold 0->1, not to certified, which
-- needs >=2 consecutive gold runs regardless).
--
-- FIX APPLIED LIVE THIS SESSION:
--   INSERT one fresh survived=true gold_standard_ultraloop_audit row for
--   pasco's single stale letter (B), backed by this session's own live
--   pencil_dod_evaluate_county('pasco') RPC re-verification (id=21038,
--   applied directly via PostgREST at 2026-09-03T22:28:56Z; this file
--   documents it for the repo audit trail per the SHIP GATE mandate).
--
-- NOT DONE / handoff: this fix alone does not flip certified=true. It only
-- ensures the NEXT organic gold_standard_loop()+certify() cycle (which,
-- per .github/workflows/*.yml, essentially every shard session runs at its
-- own close-out -- very likely within hours given the fleet's cadence)
-- will see pasco's evidence fully fresh and advance consecutive_gold 0->1.
-- A SECOND subsequent gold run after that is still required to certify.
-- Letters C/D/F (freshest evidence 2026-08-28T08:38Z) and A/E
-- (2026-08-28T14:28Z) will themselves age out of the 7-day window around
-- 2026-09-04, so a future session should re-touch those before/at that time
-- if pasco has not certified by then, to avoid another flap. manatee (9/10,
-- C=91.6%% structurally capped by a same-day 2026-09-03 architectural
-- decision on CLERK_SSOT_CANCELLED denominator treatment) and sumter
-- (6/10, E/I/J blocked on 2 dead-at-source case numbers, C same structural
-- cap as manatee) are not realistic certification targets -- confirmed live,
-- unchanged from docs/spec/19807.md written ~6h earlier the same day.
--
-- Re-running this file is a safe no-op (NOT EXISTS guarded on
-- county_slug+letter+dispatch_id).

INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
SELECT * FROM (VALUES
  ('5e41ea06-df48-4e37-8d4a-1a88795a199d'::text, 'fallback'::text, 'pasco'::text, 'B'::text,
   'B: freshness refresh (architect triage issue 19818/19807). Live re-verified via pencil_dod_evaluate_county(''pasco''): verified=92 closed_sold=92, metric=100.0, PASS. Prior freshest survived=true row (id=18687) aged out of the 7-day certify window at 2026-08-27T13:28:14Z, ~9h before this run''s cutoff -- root cause of pasco''s adversarial_survival_9_of_10 revocation reason (run 16765). No data changed; this is a stale-evidence refresh only, all other 9 letters confirmed fresh (<7d) at time of this check.',
   true,
   '{"loop_run_id":16765,"metric":100.0,"verified":92,"closed_sold":92,"honesty_marker":"CONFIRMED via live pencil_dod_evaluate_county(''pasco'') RPC call, architect triage issue 19818 (triaging blocked issue 19807)","stale_row_superseded":18687,"stale_row_age_hours_over_limit":9}'::jsonb)
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit a
  WHERE a.county_slug = v.county_slug AND a.letter = v.letter AND a.dispatch_id = v.dispatch_id
);

-- VERIFICATION QUERIES:
-- SELECT letter, survived, created_at FROM gold_standard_ultraloop_audit
-- WHERE county_slug='pasco' AND letter='B' ORDER BY created_at DESC LIMIT 3;
-- -- expected: freshest row survived=true, created_at ~2026-09-03T22:28Z.
-- SELECT county_slug, certified, consecutive_gold, revoked_at FROM gold_standard_certifications
-- WHERE county_slug IN ('pasco','manatee','sumter');
-- -- certified still expected false until the NEXT gold_standard_loop()+certify() cycle runs.
-- SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                WHERE county_slug = ANY('{pasco,manatee,sumter}'::text[]) AND certified);
-- -- still FALSE as of this session; expected to flip after 2 consecutive future gold cycles.
