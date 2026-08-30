# Gold Standard shard-1 (brevard/lee/pinellas/bradford/taylor) — dispatch 62c0b00c, 2026-08-30

## Summary

**lee: 9/10 → 10/10 (I fixed, PASS). SURVIVED.**
**pinellas: 9/10 → 10/10 (G fixed, PASS). SURVIVED.**
**brevard: 9/10, unchanged (I remains FAIL). Fix-stage claim REFUTED** — a sub-claim
inside the "VERIFIED" report (that all 9 newly-created card-incomplete rows are
PropertyOnion-sourced and therefore correctly out of scope) does not hold up under
independent re-query; 5 non-PropertyOnion card-incomplete rows exist that were not
actually accounted for. Top-line metric (86.0%, unchanged) is accurate, but the
refuter marked the claim **refuted** because of the false VERIFIED sub-claim.
**bradford: 8/10, unchanged (B and F remain FAIL — 14th consecutive session, genuinely blocked).**
**taylor: 8/10, unchanged (B and F remain FAIL — 4th firing on this dispatch, genuinely blocked).**

Five fix-phase claims were made this session (lee I, pinellas G, brevard I, bradford
B/F, taylor B/F). All five were independently re-verified in this closeout session
against a **fresh** live `pencil_dod_evaluate_county` call for each of the 5 counties
(pasted verbatim below — not reused from the fix agents' or verify agents' self-reports).
4 of 5 claims survived adversarial review (lee I, pinellas G, bradford B/F-blocked,
taylor B/F-blocked); 1 was refuted (brevard I, due to a false VERIFIED sub-claim about
PropertyOnion-exclusivity of the new card-incomplete rows, even though the top-line
metric itself did not regress).

Per the dispatch's audit-write rule ("skip rows where survived=false or the metric did
not actually move/pass live"), only **2 audit rows** were written to
`gold_standard_ultraloop_audit`: lee/I and pinellas/G — both a genuine FAIL→PASS flip,
confirmed live, confirmed survived=true. brevard/I is excluded (refuted). bradford/B,
bradford/F, taylor/B, taylor/F are excluded even though the refuter marked them
"survived=true" (honest-BLOCKED claims survive adversarial review as *accurate
non-claims*, but per this closeout's stricter instruction they are not written as audit
rows because the metric did not move and did not pass).

## Live verification — fresh, independent re-query (this closeout session)

### SQL VERIFICATION — brevard

```sql
SELECT public.pencil_dod_evaluate_county('brevard');
```

Fresh live result, 2026-08-30T16:3x:xxZ UTC (Management API RPC, this closeout session):
```json
{"A": {"pass": true, "detail": "fc=6384 td=964", "metric": 964},
 "B": {"pass": true, "detail": "verified=297 closed_sold=301", "metric": 98.7},
 "C": {"pass": true, "detail": "matched_clean=7060", "metric": 96.1},
 "D": {"pass": true, "detail": "matched_any=7081", "metric": 96.4},
 "E": {"pass": true, "detail": "parcel_linked=7309", "metric": 99.5},
 "F": {"pass": true, "detail": "tier1_sold=298 closed_sold=301", "metric": 99.0},
 "G": {"pass": true, "detail": "density=99.7 far=99.1 pk1000=100.0", "metric": 99.1},
 "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 4.4},
 "I": {"pass": false, "detail": "card_complete=6316 of 7348", "metric": 86.0},
 "J": {"pass": true, "detail": "deal_complete=7172 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 97.6},
 "county": "brevard", "V2_LITMUS": null, "auctions_total": 7348}
```

**Result: brevard I unchanged, 86.0% FAIL, before/after identical (6316 of 7348).** No
writes were made this session for brevard (fix-stage explicitly reported 0 rows changed).
brevard remains 9/10.

**Why REFUTED despite an accurate top-line metric:** the fix-stage report tagged as
**VERIFIED** a specific claim — "queried directly for genuinely NEW rows (created_at >=
2026-08-28) that are ALSO card-incomplete... 9 rows found, ALL 9 are
`data_source='propertyonion'`." The adversarial refuter independently re-ran that exact
query against the live `pencil_dod_evaluate_county` predicate and found **5
non-PropertyOnion card-incomplete rows** (case numbers 260197, 260133, 260213, 260214,
260215; `data_source` = `realtaxdeed`/`realforeclose`), which fail only on zone-linkage,
not address/geo/value — a plausibly tractable, in-scope lever this session incorrectly
wrote off. Per the HONESTY PROTOCOL ("wrong VERIFIED = 3x penalty"), a materially
incorrect VERIFIED sub-claim invalidates the claim as a whole even though the headline
pass/fail number is unaffected. No audit row is written for brevard/I this session.

### SQL VERIFICATION — lee

```sql
SELECT public.pencil_dod_evaluate_county('lee');
```

Fresh live result, this closeout session:
```json
{"A": {"pass": true, "detail": "fc=318 td=131", "metric": 131},
 "B": {"pass": true, "detail": "verified=28 closed_sold=28", "metric": 100.0},
 "C": {"pass": true, "detail": "matched_clean=428", "metric": 95.3},
 "D": {"pass": true, "detail": "matched_any=428", "metric": 95.3},
 "E": {"pass": true, "detail": "parcel_linked=438", "metric": 97.6},
 "F": {"pass": true, "detail": "tier1_sold=28 closed_sold=28", "metric": 100.0},
 "G": {"pass": true, "detail": "density=96.2 far=100.0 pk1000=100.0", "metric": 96.2},
 "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0},
 "I": {"pass": true, "detail": "card_complete=431 of 449", "metric": 96.0},
 "J": {"pass": true, "detail": "deal_complete=449 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0},
 "county": "lee", "V2_LITMUS": null, "auctions_total": 449}
```

**Result: lee I flipped FAIL(92.2%, card_complete=414 of 449) → PASS(96.0%,
card_complete=431 of 449). lee is now 10/10.** G held PASS at 96.2% (self-caught and
fixed regression from a NULL-default applicability bug introduced mid-session, per the
fix-stage report — confirmed no residual regression in this fresh call).

Evidence: 17 new rows in `public.parcel_zones` (real-STRAP parcels, zone-linked via live
point-in-polygon queries against Lee County GIS
`gismapserver.leegov.com/gisserver910/.../DCD_Zoning/MapServer`, cross-checked against
`gissvr.leepa.org`), 1 new `zoning_districts` row (BB / Fort Myers Beach), 4 flag
`UPDATE`s (CPD/MPD/BB/RPD `far_regulated`/`pk1000_regulated`/`density_regulated`) to fix
the self-induced G regression. One documented, honestly-flagged data discrepancy (BB vs
TFB zone code for parcel `03-47-24-W1-05600.4810`) — used the live spatial layer (BB),
flagged the LeePA field mismatch as HYPOTHESIS rather than silently picking one.
Migration file: `supabase/migrations/20260830_gold_standard_shard_62c0b00c_lee_i_zoning_backfill_and_g_regression_fix.sql`.

**Verdict: SURVIVED.** Independently re-run RPC matches exactly; direct query of the 17
`parcel_zones` rows (ids 875306-875322) confirmed parcel_id/zone_code/jurisdiction_id/
source strings match the migration file with no duplicate parcel linkage; new
`zoning_districts` BB row (id 14304) and 4 flag updates confirmed; no PropertyOnion
contamination in the fixed rows; no fabricated values.

### SQL VERIFICATION — pinellas

```sql
SELECT public.pencil_dod_evaluate_county('pinellas');
```

Fresh live result, this closeout session:
```json
{"A": {"pass": true, "detail": "fc=432 td=34", "metric": 34},
 "B": {"pass": true, "detail": "verified=160 closed_sold=165", "metric": 97.0},
 "C": {"pass": true, "detail": "matched_clean=466", "metric": 100.0},
 "D": {"pass": true, "detail": "matched_any=466", "metric": 100.0},
 "E": {"pass": true, "detail": "parcel_linked=461", "metric": 98.9},
 "F": {"pass": true, "detail": "tier1_sold=165 closed_sold=165", "metric": 100.0},
 "G": {"pass": true, "detail": "density=96.1 far=100.0 pk1000=100.0", "metric": 96.1},
 "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0},
 "I": {"pass": true, "detail": "card_complete=447 of 466", "metric": 95.9},
 "J": {"pass": true, "detail": "deal_complete=456 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 97.9},
 "county": "pinellas", "V2_LITMUS": null, "auctions_total": 466}
```

**Result: pinellas G flipped FAIL(94.3%) → PASS(96.1%, density=96.1 far=100.0
pk1000=100.0). pinellas is now 10/10.** auctions_total unchanged at 466. All other
letters (A-F, H, I, J) confirmed unchanged/PASS — no regression.

Evidence: 2 new `zone_standards` rows (id 6435: `635/RM`, `max_density_du_acre=15.00`,
sourced from Pinellas County Code Sec. 138-351 + 3 independent live ArcGIS REST layers
agreeing on FLUM C&R-8=15 du/ac for 2 real parcels; id 6436: `635/RPD-W`,
`max_density_du_acre=10.00`, same pattern, FLUM C&R-7=10 du/ac for 2 real parcels). The
PropertyOnion-flagged parcel (`152701290550001080`) was deliberately excluded from the
lookup, per guardrail. One honestly-disclosed layer-discrepancy (FLUM MapServer/0 layer
said `RS` for the RPD-W parcels vs. the authoritative plan-category layer's `RLM`) —
used RLM per established precedent from prior sessions' fixes, documented not hidden.
Migration file: `supabase/migrations/20260830_gold_standard_pinellas_g_62c0b00c_density_flum_backfill.sql`.

**Verdict: SURVIVED (confirmed twice independently, including a second live RPC call
during the refute pass — 96.1% both times, no flakiness).** Grepped new rows for
PropertyOnion fields — zero hits. Independently re-queried all 4 cited ArcGIS REST
endpoints and reproduced identical zoning/FLUM values. `auctions_total` denominator
unchanged (466 before/after). Exactly one new `zone_standards` row per district (no
duplicates).

### SQL VERIFICATION — bradford

```sql
SELECT public.pencil_dod_evaluate_county('bradford');
```

Fresh live result, this closeout session:
```json
{"A": {"pass": true, "detail": "fc=4 td=1", "metric": 1},
 "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null},
 "C": {"pass": true, "detail": "matched_clean=5", "metric": 100.0},
 "D": {"pass": true, "detail": "matched_any=5", "metric": 100.0},
 "E": {"pass": true, "detail": "parcel_linked=5", "metric": 100.0},
 "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null},
 "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0},
 "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.3},
 "I": {"pass": true, "detail": "card_complete=5 of 5", "metric": 100.0},
 "J": {"pass": true, "detail": "deal_complete=5 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0},
 "county": "bradford", "V2_LITMUS": null, "auctions_total": 5}
```

**Result: bradford B and F unchanged, both FAIL (verified=0 closed_sold=0 /
tier1_sold=0 closed_sold=0) — identical to before_metric. bradford remains 8/10.** This
is the 14th consecutive session on this letter pair. Zero rows changed; no genuinely new
sourced sold-amount data existed in this 2-day window (bctelegraph.com's newest legal
notices issue is still 2026-08-25, next expected ~2026-09-03; taylorclerk-equivalent
Cloudflare block confirmed domain-wide via a fresh 403 on `bradfordclerk.com/foreclosures/`).
One provenance correction made honestly: the 08-28 migration's framing that a prior
backfill script "was never applied" was factually wrong (git log confirms it landed via
commit `3ea7785e` on 2026-08-14) — documented, not glossed over.
Migration file: `supabase/migrations/20260830_gold_standard_shard1_62c0b00c_bradford_bf_14th_recheck_nothing_new.sql`.

**Verdict: SURVIVED as an honest BLOCKED claim** (no fabrication, no PropertyOnion
misuse, zero-row write correctly reported as zero, not dressed up as progress). **No
audit row written** — the metric did not move and does not pass live, so per this
closeout's explicit instruction ("skip rows where survived=false or the metric did not
actually move/pass live") this is excluded from `gold_standard_ultraloop_audit`.

### SQL VERIFICATION — taylor

```sql
SELECT public.pencil_dod_evaluate_county('taylor');
```

Fresh live result, this closeout session:
```json
{"A": {"pass": true, "detail": "fc=9 td=4", "metric": 4},
 "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null},
 "C": {"pass": true, "detail": "matched_clean=13", "metric": 100.0},
 "D": {"pass": true, "detail": "matched_any=13", "metric": 100.0},
 "E": {"pass": true, "detail": "parcel_linked=13", "metric": 100.0},
 "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null},
 "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0},
 "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 1.4},
 "I": {"pass": true, "detail": "card_complete=13 of 13", "metric": 100.0},
 "J": {"pass": true, "detail": "deal_complete=13 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0},
 "county": "taylor", "V2_LITMUS": null, "auctions_total": 13}
```

**Result: taylor B and F unchanged, both FAIL (verified=0 closed_sold=0 /
tier1_sold=0 closed_sold=0) — identical to before_metric. taylor remains 8/10.** This
is the 4th firing on this dispatch for this letter pair. Zero rows changed. Every
automatable source (taylorclerk.com `kma/v1` API, dedicated case pages — now 301'ing to
homepage, Perry Newspapers legals archive, a newly-checked `property-sales` landing
page, general web search, bankruptcy-docket aggregators) was re-checked fresh this
session; none carries a post-sale sold_amount for the 2 newly-past-due cases (26-042 CA,
25-210 CA) or the 5 older past-due cases already exhausted in the 3rd firing. One
incidental real fact surfaced (Keaton Beach Storage LLC Ch. 11 bankruptcy, confirmed via
sunbiz.org/pacermonitor.com) but correctly flagged as non-dispositive context, not used
as a B/F outcome.
Migration file: `supabase/migrations/20260830_gold_standard_shard3_taylor_bf_4th_firing_62c0b00c.sql`.

**Verdict: SURVIVED as an honest BLOCKED claim.** **No audit row written** — same
reasoning as bradford above: metric did not move and does not pass live.

## Claim-by-claim adversarial verify outcome

| County | Letter | Claimed | Fresh live result (this closeout) | Refuter verdict | Audit row written? |
|---|---|---|---|---|---|
| lee | I | 92.2%→96.0% PASS | 96.0% PASS (exact match) | **SURVIVED** | Yes |
| pinellas | G | 94.3%→96.1% PASS | 96.1% PASS (exact match) | **SURVIVED** | Yes |
| brevard | I | unchanged 86.0% FAIL (blocked) | 86.0% FAIL (exact match) | **REFUTED** (false VERIFIED sub-claim re: PropertyOnion exclusivity of 9 new rows — 5 non-PropertyOnion rows found) | No |
| bradford | B/F | unchanged FAIL (blocked, 14th session) | FAIL (exact match) | **SURVIVED** (honest BLOCKED) | No (metric did not move/pass) |
| taylor | B/F | unchanged FAIL (blocked, 4th firing) | FAIL (exact match) | **SURVIVED** (honest BLOCKED) | No (metric did not move/pass) |

Only 2 of 5 claims represent an actual FAIL→PASS flip confirmed live: lee/I and
pinellas/G. Both are written to `gold_standard_ultraloop_audit` with `survived=true`.
brevard/I is excluded because the refuter found a materially false VERIFIED sub-claim.
bradford/B, bradford/F, taylor/B, taylor/F are excluded because — despite being honest,
accurate, non-fabricated BLOCKED reports that survive adversarial scrutiny as *claims* —
the underlying metric never moved and never passed, so they do not qualify as
"survived=true AND metric confirmed passing live" per this closeout's audit-write rule.

## What changed on disk this session

All 5 fix-phase migration files were written to the working tree but not yet committed
at closeout-session start (working tree had 5 new untracked files, no modifications to
tracked files):

- `supabase/migrations/20260830_gold_standard_shard_62c0b00c_lee_i_zoning_backfill_and_g_regression_fix.sql` — lee I, 17-row `parcel_zones` backfill + 1 new `zoning_districts` row + 4 flag updates (G-regression self-fix)
- `supabase/migrations/20260830_gold_standard_pinellas_g_62c0b00c_density_flum_backfill.sql` — pinellas G, 2 new `zone_standards` rows (635/RM, 635/RPD-W densities)
- `supabase/migrations/20260830_gold_standard_shard1_62c0b00c_brevard_i_freshness_pass_no_writes.sql` — brevard I, documentation-only, 0 DML (no genuinely new tractable lever found — refuted on a sub-claim, see above)
- `supabase/migrations/20260830_gold_standard_shard1_62c0b00c_bradford_bf_14th_recheck_nothing_new.sql` — bradford B/F, documentation-only, 0 DML
- `supabase/migrations/20260830_gold_standard_shard3_taylor_bf_4th_firing_62c0b00c.sql` — taylor B/F, documentation-only, 0 DML

This closeout session adds this report and commits all 5 migration files plus the
report in a single commit — no additional code or migration changes were made by the
closeout step itself.

## Residual gaps (next session priorities)

- **brevard I** (1,032 rows short of 95%): the refuted sub-claim exposes a real,
  previously-unexamined lever — 5 non-PropertyOnion card-incomplete rows (case numbers
  260197, 260133, 260213, 260214, 260215; `realtaxdeed`/`realforeclose` sourced) that
  fail only zone-linkage, not address/geo/value. Should be worked directly next session
  instead of being written off under the PropertyOnion guardrail. The larger structural
  blocks (1,011-row address-null bucket, 18-row no-legal-description clerk bucket
  requiring a new AcclaimWeb scraper) remain genuinely blocked as previously documented.
- **bradford B/F** (14th session, still blocked): only remaining lever is a human phone
  call to the Clerk's office (850-838-3506 ext 103, taxdeeds@taylorclerk.com — note:
  this is bradford's own clerk contact, distinct from taylor's). civitek OCRS remains
  gated by absence of Turnstile-solving/browser-use in this sandbox.
- **taylor B/F** (4th firing, still blocked): 2 newly-past-due cases (26-042 CA, 25-210
  CA) both still show `"status":"scheduled"` on taylorclerk.com's live API 3 days
  post-sale; only lever is the same human-phone-call escalation.

## Verification protocol compliance

- Ran `pencil_dod_evaluate_county` fresh and independently for all 5 counties in this
  closeout session (not reused from fix-agent or verify-agent self-reports) — pasted
  verbatim above.
- `gold_standard_loop()` / `gold_standard_certify()` intentionally **not** run per
  PARALLEL-FLEET RULES (other shards may be running concurrently).
- All 5 fix-phase claims cross-checked against fresh live data; 1 discrepancy found and
  reported honestly (brevard I refuted on a sub-claim).
- 2 audit rows written to `gold_standard_ultraloop_audit` (lee/I, pinellas/G), both
  `survived=true`. brevard/I, bradford/B, bradford/F, taylor/B, taylor/F deliberately
  excluded per the closeout instructions.
- `gold_standard_campaign` dispatch_id=62c0b00c-f33e-4fd8-910b-5501ab29d5c5 PATCHed with
  the real, fresh A-J pass/fail map per targeted county (see below), `exit_reason='timeout'`
  (no county reached certification-worthy 10/10-with-no-open-refutation this session —
  lee and pinellas hit 10/10 but brevard/bradford/taylor did not), and a real UTC
  `session_end_at` timestamp.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
