-- ARCHITECT TRIAGE for issue #18319 (dispatch 1338ab5d, SHARD-4:
-- sarasota/seminole/pasco/suwannee/hendry)
--
-- DoD (SELECT EXISTS gold_standard_certifications.certified for the 5 counties)
-- re-verified live: FALSE. All 5 certified=false as of this triage.
--
-- DIAGNOSIS (VERIFIED live, PostgREST + gold_standard_ultraloop_audit):
-- Attempt 1/1 (GHA run 31159912812, 08:00-08:58Z) DID execute real work live
-- against Supabase (confirmed via 16 gold_standard_ultraloop_audit rows,
-- dispatch_id=1338ab5d-c22a-43be-876f-887fb75417e7, created_at 08:56:56Z) --
-- this was NOT an OAuth-wall fast-fail like the #18063 precedent. Real fixes
-- landed: seminole G (PUD-RES zone_standards classified not-regulated,
-- 88.9%->97.9% survived), pasco C/D/F (RealForeclose/RealTaxDeed harvest+match,
-- survived=true), hendry C/D/E/I/J (Hendry ArcGIS parcel linkage, survived=true
-- at session time). A PR branch (claude/issue-18319-20260807-0800) was created
-- with the executor script + migration but never merged -- irrelevant to the
-- DoD since the fixes were applied live via PostgREST, independent of git.
--
-- Live re-query at this triage (5.5h after the session) shows drift, NOT a
-- reversion bug: every county's auction denominator keeps growing (new
-- foreclosure/tax-deed rows arrive continuously), so letters that measure
-- coverage-of-denominator (I card-completeness, J deal-completeness, B
-- verified-vs-closed-sold) regress as new rows arrive without matching
-- enrichment. Confirmed per-county, per-letter:
--   sarasota (9/10): G fails -- density=93.0 (pk1000 already fixed to 100.0
--     by a separate prior session). Same root cause class as pk1000: Sec.
--     124-120 density/FAR is use-type-keyed in some CN/PID/CT/DTC districts,
--     genuinely no district-wide value in the ordinance text. 4th+ consecutive
--     session flagging this exact structural gap -- requires Ariel policy
--     decision (exclude use-type-only districts from applicability, or accept
--     a confidence<1.0 modal proxy).
--   seminole (9/10): I fails -- card_complete=130/137 (94.9%, need ~95%).
--     Root cause independently reconfirmed identical to sibling issue #18063's
--     5th firing (decision_log id=1065, same day): genuine unincorporated-zoning
--     linkage gap, no live ArcGIS endpoint covers the remaining parcels. Real
--     data-acquisition work, not a mechanical fix.
--   pasco (9/10): I fails -- card_complete=271/327 (82.9%). Same class as
--     seminole I -- real parcel/geo enrichment work, ~56 rows short.
--   suwannee (7/10): B fails (0/4, was passing at session time on a 0/0
--     vacuous-pass -- 4 new sales closed since with none verified: NOT a
--     regression, a newly-materialized real gap). I fails (74.3%). J fails
--     (0%). B/F were previously flagged structural (courthouse-steps FC +
--     Cloudflare Turnstile on myfloridacounty.com/orisearch/61) -- 6th+
--     consecutive session; F now separately passes live (tier1_sold=4 of
--     4 closed) but B's verification gap is the real remaining blocker.
--   hendry (9/10): J fails -- deal_complete=38/60 (63.3%). Was passing at
--     session time (denominator was 38, all matched); 22 new auctions
--     arrived since with no bid_decisions computed for them.
--
-- FABRICATION CHECK (VERIFIED, no action taken): confirmed live that the
-- committed-but-unmerged executor script's generate_bid_decisions() helper
-- (assessed_value proxy for ARV, constant ml_score=0.55, formula-derived
-- cma_resale=arv/cma_distressed=arv*0.85) was NEVER actually executed against
-- bid_decisions for hendry or suwannee -- SELECT ... WHERE arv_source ILIKE
-- '%18319%' returns 0 rows. This is exactly the "ghost success" pattern
-- purged 3+ times fleet-wide already (20260721 hillsborough/glades/suwannee
-- J purge, 20260711 suwannee FC repurge, levy/dixie purges) -- constant
-- ml_score across all rows, formula CMA instead of real comps, is fabrication
-- per the campaign's own ghost-success ban. Declined to run this helper to
-- mechanically close hendry/suwannee J: doing so would recreate the exact
-- anti-pattern already flagged and reverted elsewhere in this fleet, and the
-- resulting rows would not survive a future adversarial audit. Flagging for
-- the next engineer session: build/reuse a REAL per-property CMA+ML pipeline
-- (gen_valuations_comps_batch / Shapira V14 scoring) for hendry's 22 and
-- suwannee's J gap, not the proxy-formula generator on this branch.
--
-- No county reached 10/10 this triage -- unlike sibling issue #18063 (5th
-- firing, decision_log id=1065, same day), this is NOT a certify-freshness-
-- refresh case (no county holds 10/10 PASS to refresh evidence for).
--
-- cc_redispatch_guard(18319) is genuinely exhausted (attempts=1/max_attempts=1,
-- status=blocked) after ONE real, productive session -- not a stuck/wall
-- artifact. Reactivating for one more real 6h+ engineer session to continue
-- the genuine residual data-acquisition work (seminole/pasco I zoning-linkage,
-- hendry/suwannee J real CMA/ML scoring, suwannee I address-match enrichment).
-- sarasota G and suwannee B/F remain flagged as requiring an Ariel policy
-- decision or genuine electronic-record availability -- not something any
-- number of further automated sessions can resolve.
UPDATE public.cc_redispatch_guard
SET status = 'active',
    max_attempts = 2,
    last_error = 'architect_triage_18319: attempt 1 did real, verified work '
                 '(seminole G, pasco C/D/F, hendry C/D/E/I/J) but none of the '
                 '5 counties reached 10/10 -- genuine residual data-acquisition '
                 'work remains (seminole/pasco I zoning-linkage, hendry/suwannee '
                 'J real CMA/ML scoring -- explicitly NOT the proxy-formula '
                 'ghost-success generator already purged 3x fleet-wide). '
                 'sarasota G + suwannee B/F remain structural, need Ariel policy '
                 'decision or real sale-record availability. Reactivated for one '
                 'more real engineer session.'
WHERE issue_number = 18319
  AND status = 'blocked';

-- Verification query (run after apply):
-- SELECT issue_number, status, attempts, max_attempts, last_error
-- FROM public.cc_redispatch_guard WHERE issue_number = 18319;
