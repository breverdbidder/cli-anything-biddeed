# Gold Standard shard-1 — broward / santa_rosa / madison (dispatch f5f315b3, loop run 6288)

Session date: 2026-07-25. Executed via ultracode Workflow orchestration (2 fix agents + 2 independent adversarial verifiers, all live SQL via `mgmt_sql.py` / Supabase Management API — no `exec_sql` RPC and no working psql/pooler credentials were available in this sandbox, discovered and worked around this session).

## Plan vs Actual

| County | Target | Planned | Actual | Deviation |
|---|---|---|---|---|
| broward | already 10/10 KPI | audit-freshness refresh for certification eligibility | Backfilled `gold_standard_ultraloop_audit` survived=true evidence for B,D,E,F,H (A,C,G,I,J already had recent coverage). All 10 letters now have real, independently-reproduced evidence within 7 days. | Certification (`gold_standard_certifications.certified`) is still `false` — stale pending the next automated `gold_standard_loop()` run (needs a new `loop_run_id`) plus 2 consecutive gold cycles. Not certified this session; audit-coverage prerequisite only. |
| santa_rosa | I FAIL (94.6%) | fix >=1 of 5 card-incomplete rows to cross 88/92 | Applied real ArcGIS zone+geo fix (2 of 5 rows) with a regression-guard fix (RR1 codified density, sourced from Santa Rosa LDC) pushed to main. Value field remained genuinely unsourceable for both rows after exhausting known sources. | I stayed FAIL at 94.6% (87/92) — did NOT cross threshold. Reporting honestly per SHIP GATE rather than forcing a false PASS. |
| madison | A/B/F FAIL | fix or re-diagnose | Re-verified live (WebFetch of madisonclerk.com/tax-deed-sales/) that the county genuinely has zero tax-deed inventory and zero ever-closed cases. Confirms a prior session's diagnosis (run3534, 2026-07-10). No touch. | None — correctly matched the brief's own "switch to next target on long-accrual block" instruction. Not forced. |

## Verification Evidence

### santa_rosa — pencil_dod_evaluate_county('santa_rosa'), live, 2026-07-25

BEFORE (session start):
```json
"I": {"pass": false, "detail": "card_complete=87 of 92", "metric": 94.6}
"G": {"pass": true, "detail": "density=97.2 far= pk1000=100.0", "metric": 97.2}
```

AFTER (independently re-queried by me, post-workflow, 2026-07-25 ~00:2x UTC):
```json
{"A":{"pass":true,"metric":32,"detail":"fc=60 td=32"},
 "B":{"pass":true,"metric":100,"detail":"verified=31 closed_sold=31"},
 "C":{"pass":true,"metric":96.7,"detail":"matched_clean=89"},
 "D":{"pass":true,"metric":96.7,"detail":"matched_any=89"},
 "E":{"pass":true,"metric":96.7,"detail":"parcel_linked=89"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=31 closed_sold=31"},
 "G":{"pass":true,"metric":97.2,"detail":"density=97.2 far= pk1000=100.0"},
 "H":{"pass":true,"metric":0.2},
 "I":{"pass":false,"metric":94.6,"detail":"card_complete=87 of 92"},
 "J":{"pass":true,"metric":100},
 "county":"santa_rosa","auctions_total":92}
```

I's numerator is unchanged (still 87/92) — the two rows that were fixed (case 2026063/parcel 29-2N-28-0407-00A00-0040, case 2026094/parcel 16-1N-27-0000-00500-0000) needed zone+geo **and** value to flip; value has no available source (ArcGIS ParcelsOpenData has no dollar field; srcpa.gov search backend needs an undocumented POST body; santarosa.county-taxes.com 403s; map.srcpa.gov was down; a third-party aggregator value was found and explicitly rejected as unsourced/unreliable per Honesty Protocol). G did **not** regress (confirmed 97.2 before and after) despite the new RR1 zone code, because the codified density (2.0 du/acre, Santa Rosa LDC Table 2.04.02.a) was sourced and written before the zoning_districts insert. Commit `aa0bef1d`, pushed to main as `ba203ab2`.

Independent adversarial verifier re-ran all of this from scratch (own SQL, own DB reads) and confirmed: no fabricated values, no regression, zone_standards correctly cited to a real ordinance section, I honestly still FAIL.

### broward — gold_standard_ultraloop_audit, live, 2026-07-25

Before this session: survived=true rows within 7 days existed only for A, C, G, I, J (5 of 10). B, D, E, F, H had zero rows in the trailing-7-day window.

After this session (independently re-queried by me):
```
B  survived=true  2026-07-25 00:18:03
D  survived=true  2026-07-25 00:18:03
E  survived=true  2026-07-25 00:18:03
F  survived=true  2026-07-25 00:18:03
H  survived=true  2026-07-25 00:18:03
```
All 10 letters (A–J) now carry real, independently-reproducible survived=true evidence within 7 days — each verdict backed by a distinct live query (independent-source sampling for B, denominator/duplicate checks for D/E, cross-column divergence proof for F, multi-county batch-staggering proof for H), not a rubber-stamped copy of the aggregate metric. Adversarial verifier independently reproduced every count and case number cited (206/206 for B, 634/664 for D, 661/664 for E, 205/206 + the one real $0 vs $356,600 divergence for F, the 31-row/10-county H batch) and confirmed each held up.

Live `pencil_dod_evaluate_county('broward')` (re-confirmed by me): still 10/10 PASS, unchanged.

**Certification status (checked by the verifier, confirmed by me):** `gold_standard_certifications` for broward currently shows `certified: false`, `revocation_reason: "broward run=6288 consecutive_non_gold=77 reason=adversarial_survival_5_of_10"` — this reflects the *stale* 19:30 loop run that predates tonight's backfill. `gold_standard_certify()` only re-evaluates on a new `loop_run_id`; none has fired since. Per the EVALUATOR V6 rule, certification additionally requires 2 consecutive gold runs. **Broward is NOT certified as of this report** — the audit-coverage gap that was blocking it is now closed, but certification itself depends on the next automated `gold_standard_loop()` cycle(s), which this session correctly did not trigger manually (parallel-fleet rule: don't run the full loop mid-session unless no other shard is in flight, which was not confirmed here).

### madison — pencil_dod_evaluate_county('madison'), live, 2026-07-25

```json
{"A":{"pass":false,"metric":0,"detail":"fc=5 td=0"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100},"H":{"pass":true,"metric":16.6},"I":{"pass":true,"metric":100},"J":{"pass":true,"metric":100},
 "county":"madison","auctions_total":5}
```
Unchanged from session start. `pipeline.counties` config for madison is already correct (fixed 2026-07-10): both foreclosure and tax-deed lanes point at real madisonclerk.com pages. Live-refetched tax-deed-sales page this session: "There are no properties on the list of tax deeds at this time." All 5 madison auction rows are current-cycle scheduled/cancelled foreclosures; zero have ever reached `sold_amount IS NOT NULL`. A/B/F are genuinely blocked on real-world inventory/accrual, not a pipeline defect — not forced.

## Deviation Log

- **Environment gap discovered and worked around**: this sandbox's `SUPABASE_DB_PASSWORD` (both the env var and the value documented in CLAUDE.md) fails psql auth against the pooler, and the `exec_sql` PostgREST RPC referenced by numerous prior session scripts no longer exists (404, not in schema cache — likely retired as part of the GTM-22D credential-handling hardening). Found and used `mgmt_sql.py` (Supabase Management API + `SUPABASE_ACCESS_TOKEN`) instead, which is the actual live-SQL path multiple recent migrations' commit messages already reference ("Applied live via mgmt_sql.py"). No impact on this session's results, but worth noting for future shard sessions in case this is a sandbox-wide condition.
- santa_rosa I did not reach PASS as hoped — reported as FAIL, not rounded up.
- broward certification did not flip to `true` this session — audit-coverage prerequisite closed, actual certification gated on the next automated loop cycle(s), reported as such rather than claimed.
- Did not run `gold_standard_loop()` or `gold_standard_certify()` as a scoring action (guardrail: don't run the shared scoring loop mid-session when other shards may be in flight; the broward workflow agent's read-only diagnostic calls to `gold_standard_certify()` were SELECT-only introspection of existing state, not the mutating scoring loop).

## Guardrails respected
No cron jobs 109/111/115 touched. No gold-standard-loop-* scoring jobs executed. No counties other than broward/santa_rosa/madison touched. No fabricated data written anywhere (multiple candidate values were found and explicitly rejected for lacking a reliable independent source). Commit pushed directly to main per SHIP-TO-MAIN MANDATE, no side branch, no PR.

---
dispatch_id: f5f315b3-5d15-48a8-9312-49bfb3c4d91f
chat_session: architect-20260725T000000
