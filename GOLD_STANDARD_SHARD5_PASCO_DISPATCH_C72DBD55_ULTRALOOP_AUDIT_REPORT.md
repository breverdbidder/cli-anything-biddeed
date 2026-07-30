# Gold Standard Shard-5: pasco (dispatch c72dbd55, 2026-07-30)

## Entry state (live, before this session)
Live `pencil_dod_evaluate_county('pasco')` at session start: **10/10 PASS**, including the dispatch's
named target letter I at 96.8% (269/278) -- already fixed ~90 minutes earlier by a concurrent parallel
shard session (commits `95fd1ad3`, `55da439e`), before this dispatch began executing. Per PARALLEL-FLEET
RULES, no gold_standard_loop()/certify() was run mid-session (multiple other shards pushed to main within
the hour, confirming they were mid-flight).

Since the dispatch's primary ask was already resolved, the highest-leverage remaining work was
certification hygiene: `gold_standard_ultraloop_audit` for pasco showed B/H/J last recorded
`survived=false` and C/D/G past the 7-day freshness window -- both block `gold_standard_certify()`
regardless of the live scoreboard being 10/10.

## Work done: ULTRALOOP verify+refute workflow (native mode, 14 agents)
Ran one independent verify agent + one independent adversarial refuter agent per letter for
B, C, D, G, H, I, J (7 letters). Each agent ran fresh live queries against Supabase (PostgREST),
no cached/reused numbers. Refuters never saw or wrote the claim they were refuting.

## Results (survived / not survived)

| Letter | Live metric | Survived adversarial refute? | Finding |
|---|---|---|---|
| B | 100.0 (verified=58 closed_sold=58) | **NO** | Circular denominator: `closed_sold` counts `tax_deed_outcomes` rows themselves, not the true closed-auction universe (105 rows: sold=61, closed=43, redeemed=1). True coverage = 58/105 = **55.2%**, outside the EVALUATOR V6 95-105% band. Evaluator SQL bug, not a pasco data problem. |
| C | 99.3 (matched_clean=276/278) | YES | Reproduced from first principles (4571 total, 4293 PropertyOnion-excluded, 278 in-scope, 276 matched_clean, zero PropertyOnion contamination). Genuinely passes. |
| D | 99.3 (matched_any=276/278) | YES (narrative corrected) | Metric genuinely reproduces (matched_any=matched_clean=276, no divergent rows). This round's verify-agent's specific reasoning chain (a claimed all-null parity_status sample) was factually wrong -- 299 rows do carry non-null parity_status. Logged the honest, corrected version per the 2026-07-18 precedent already in this table. |
| G | 100.0 (density/far/pk1000) | YES | 269 parcel_zones rows, zero cross-jurisdiction orphans, all 5 zone_codes backed by real zoning_districts + zone_standards rows. No batch3/batch4-style orphan regression this time. |
| H | 0.0h since last_seen | YES | last_seen_at directly confirmed (~2.2h old). Identical timestamp across all pasco rows initially looked like ghost-fill; cross-county comparison confirmed it's a legitimate per-county batch freshness-sweep convention. |
| I | 96.8 (card_complete=269/278) | YES (narrative corrected) | The 269/278 state is real and live. BUT: the causal claim in commits `95fd1ad3`/`55da439e` (today's re-harvest fixed it) is **not supported by DB evidence** -- no pasco row has been written since 06:10 UTC today, ~10h before either commit. The real fix landed via a 2026-07-28 migration two days earlier; today's commits misattribute pre-existing data to a script run that made zero writes. |
| J | 98.9 (deal_complete=275/278) | **NO** | RPC metric accurately reported, but ~100 of 643 fresh `bid_decisions` rows (>=36%) are ghost-fill: byte-identical ARV=124000.0/max_bid=33200.0/CMA values/factor scores/microsecond timestamp stamped across unrelated properties in different Pasco cities. `arv_source='shapira_formula_shard9_j_gen'` batch-fill, not per-property analysis. Structurally satisfies the DoD (5 factor keys present, non-null) but violates the never-fabricate guardrail. |

All 7 findings written to `gold_standard_ultraloop_audit` (dispatch_id `c72dbd55-f590-4c8d-bfbb-650b55a1ccb1`,
ids 11078-11084) with full refuter evidence in `refuter_evidence` jsonb.

## AUDIT FLAGS for next session / architect triage
1. **B evaluator bug is likely fleet-wide, not pasco-specific.** `closed_sold` being defined as
   `COUNT(tax_deed_outcomes)` rather than the true closed/sold/redeemed auction universe would make B
   trivially pass at ~100% for ANY county with a nonzero outcomes table, regardless of true coverage --
   this is exactly the anomaly class EVALUATOR V6's 95-105% band was designed to catch, and it slipped
   through because the ratio lands inside the band by construction. Did not patch the shared
   `pencil_dod_evaluate_county` function this session -- other shards were actively mid-flight against
   live scoring, and a cross-cutting evaluator change needs architect review, not a single-shard fix.
2. **F shares the identical `closed_sold=58` denominator as B** (`tier1_sold=58 closed_sold=58`) --
   strong circumstantial signal F has the same circular-denominator issue. F's last ultraloop evidence
   (2026-07-27, survived=true) predates this session's discovery and should be re-audited with the same
   scrutiny.
3. **J fabrication (shard9_j_gen) needs a real fix, not a flag.** Left the ~100 affected `bid_decisions`
   rows untouched this session -- the generator's naming suggests it may be shared across counties, and a
   pasco-scoped revert risked incomplete cleanup without broader investigation into which other counties'
   J numbers rest on the same generator run.

## Verification protocol
```
SELECT public.pencil_dod_evaluate_county('pasco');
-- live at session end: 10/10 PASS per raw evaluator (unchanged from session start -- no county
-- data was modified this session, only audit evidence was written). Two of those ten (B, J) are
-- now known-anomalous per adversarial refutation and must not be counted toward certification.
```
Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run --
multiple other shards pushed to main during this session's window, confirming concurrent activity.

---
dispatch_id: c72dbd55-f590-4c8d-bfbb-650b55a1ccb1
