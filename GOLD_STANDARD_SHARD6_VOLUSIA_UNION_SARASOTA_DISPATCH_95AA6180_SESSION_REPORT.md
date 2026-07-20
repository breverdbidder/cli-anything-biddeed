# GOLD STANDARD shard-6 (volusia, union, sarasota) — session report

dispatch_id: `95aa6180-826c-4bd0-8442-58da4023282d` · chat_session: `architect-20260720T160000` · 2026-07-20

mode: ULTRALOOP native (Workflow tool: 3 fix leads + 3 independent adversarial refuters, 6 subagents, for sarasota; volusia/union worked inline in the orchestrating session with the same tooling)

## Summary

The dispatch brief reported volusia 10/10, union 8/10, sarasota 3/10. Live re-query at session start
confirmed union and sarasota exactly, but **volusia's 10/10 was stale and partially fabricated** —
its `gold_standard_certifications` row had already been revoked 2026-07-17 with `consecutive_non_gold=24`,
and one letter (G) had an unresolved 2026-07-19 adversarial refutation that was never followed up. This
session found the concrete fabrication, purged it (honest regression), then spent the rest of the budget on
sarasota, which had real, achievable gains once you separate "genuinely unfixable this session" (J, most of
C/D/G) from "actually just unharvested" (B/F, and a real GIS substrate for G/I).

**Net honest scoreboard, this session:**
- volusia: 10/10 (fabricated) → **8/10** (real) — G, I honestly demoted
- union: 8/10 → **8/10**, unchanged — confirmed still structurally blocked (see below)
- sarasota: 3/10 → **5/10** — B and F flip to real PASS; C/D/G/I move honestly closer without crossing
  the 95% bar; J stays honestly blocked

## Part 1 — volusia: ghost-success purge (G, I)

`gold_standard_certifications` for volusia showed `certified=false, revoked_at=2026-07-17,
revocation_reason='volusia run=5427 consecutive_non_gold=24 reason=adversarial_survival_9_of_10'` — i.e.
9 of volusia's 10 letters had fresh adversarial evidence, one didn't. Tracing `gold_standard_ultraloop_audit`
found it: letter G's 2026-07-19 refuter (id=7299) called the live evaluator's `LEAST(100,NULL,NULL)=100`
result "likely ghost-success" and marked `survived=false`, but no session since had re-investigated —
certification stayed blocked on a half-finished question.

Independent re-audit this session found the concrete answer, and it's a different (much simpler) bug than
the refuter's stated theory: **100% of volusia's 432 zoned parcels trace to one fabricated
`zoning_districts` row** (id=10678, `name='Single Family Residential (Beta Synthetic)'`,
`description='Synthetic R-1 district for 6county beta gold standard'`, `source_url=NULL`), hardcoded to
Daytona Beach/R-1 regardless of each parcel's real jurisdiction (DeLand, Deltona, Ormond Beach, Port Orange,
New Smyrna Beach, etc. all collapsed into it), inserted in 3 single-microsecond bulk batches
(339+77+16=432) on 2026-06-23. This is the **identical fabrication signature** already purged from sarasota
on 2026-07-18 (same "Beta Synthetic" self-label, same root-cause batch job, different county) — see
`GOLD_STANDARD_SARASOTA_NASSAU_BAY_GULF_DISPATCH_9F070F2B_3RD_FIRING_SESSION_REPORT.md`. I cascades from the
same rows (`v_zoning_gold_standard_card` requires a real `zone_code` match).

Purged live via `migrations/20260720_gold_standard_shard6_run5361_volusia_g_i_ghost_success_purge.sql`
(commit `a7d923b6`). A/B/C/D/E/F/H/J were independently re-verified 2026-07-19 (dispatch `0e84dad2`) and
are unaffected — real, not touched.

**Scope flag (not acted on, out of shard authority):** the same `"(Beta Synthetic)"` /
`"(ShardN Synthetic)"` / `"(UNCITED placeholder)"` label family exists today in `zoning_districts` for at
least pinellas, escambia, monroe, glades, hamilton, sumter, franklin, seminole, calhoun, washington, and
Freeport/Paxton (Walton) jurisdictions (ids 10680-10685, 10716, 10718, 10798-10806, 10828, 11068, 11104,
11163, 11203, 10673-10674) — none of these are in this shard and none were touched.

## Part 2 — union: reconfirmed structurally blocked (B, F)

Fifth independent re-check today (following the 4th-firing dispatch `1a211136` at 2026-07-20T01:30Z, same
day). `multi_county_auctions` for `county='union'`: 1 redeemed cert (`UNION-TD-CERT223`, 2026-03-12, no sale
occurred) + 2 upcoming foreclosures (`63-2025-CA-0053` due 2026-08-13, `63-2024-CA-0047` due 2026-10-15).
`closed_sold=0` genuinely — zero cases have concluded with a sale. Nothing to do until a real auction closes;
earliest possible is 2026-08-13 (24 days from this session).

## Part 3 — sarasota: real gains via ULTRALOOP fan-out (3 fix leads + 3 adversarial refuters)

Sarasota has been legitimately failing since the 2026-07-18 ghost-success purge (10/10→3/10, see the
3rd-firing report referenced above). This session ran three independent research+fix leads via the Workflow
tool, each immediately followed by its own adversarial refuter re-running every claim from scratch against
live production:

### B/F — REAL PASS (survived independent verification)
Live-harvested sarasota's `sarasota.realtaxdeed.com` and `sarasota.realforeclose.com` "Auction Results
Report" (`report_id=18`), the same technique already proven for hendry/santa_rosa. Wrote 58
`tax_deed_outcomes` + 39 new `foreclosure_outcomes` rows (all real `source_url`, 47 distinct `winning_bid`
values $4,600–$30,500, no fixed ratio). Two cases were honestly corrected from a prior pre-sale guess to the
real sold amount (`2025 CA 003116 NC` → $1,002, `2025 CA 004098 NC` → $187,101) — a fabricator would have
copied the existing value, not overwritten it. Commit `8ca5328a`.

### C/D — honest ceiling documented (still FAIL, real number moved 10%→37.2%)
Same harvest moved matched_clean/matched_any from 34→127 of 341 (37.2%). Independently reconciled the
remaining ceiling: 214 unmatched rows = 190 tax_deed (120 upcoming/future-dated + 70 redeemed — structurally
unmatchable pre-sale) + 24 foreclosure (14 cancelled + 2 completed + 8 upcoming-but-past-dated). Reaching 95%
requires either those 190 tax_deed sales to actually occur and get harvested, or the cancelled/upcoming rows
to be excluded from the DoD scope — a scoring-methodology question, not something to force this session.

### G/I — real GIS substrate shipped, G stays honest FAIL (I moved 0%→41.9%)
Found a live, working ArcGIS FeatureServer (`ags3.scgov.net/.../Hosted/CountyZoning/FeatureServer/0`) and
ran real point-in-polygon zone assignment for 2 of sarasota's 3 jurisdictions (Sarasota county/city, id=824,
45 parcels/17 distinct real codes; North Port, id=941, 97 parcels/8 distinct real codes — real variance, no
blanket single-code stamping). Venice (id=933) parcels were explicitly skipped (tax-account mismatch on
point-in-polygon, not guessed). G stays honestly FAIL: the *codes* are now real, but the numeric
*standards* (max_far/density/parking) that G actually scores were not obtainable this session — the only
existing `zone_standards` rows (28, all Venice, all `source_url=NULL`) are pre-existing untrusted rows and
were correctly NOT counted or built on. I moved from 0% to 41.9% (143/341) as a direct, honest consequence
of the real zoning substrate. Commit `8d5baaa8`.

### J — honestly BLOCKED, no fix shipped
No sarasota-applicable comps exist anywhere (`hester_cma_comps` is 100% Brevard/Palm Bay addresses;
`parcel_valuations` has zero `VERIFIED`-honesty_marker rows and zero rows tagged to any county across
280,843 total). `shapira_models` v14 is a binary win/loss classifier (AUC 0.7834), not a per-property
ARV/CMA generator. The lead spot-checked the fleet's J-generator script family (30 scripts) and reproduced,
live, that even a **currently `survived=true`** audit row (lee, id=7908) is built on a hardcoded
`ML_SCORE=0.55` / `cma_distressed = arv*0.87` (exact ratio on every sampled row) — i.e. the same fabrication
class already purged from sarasota once, still present and uncaught elsewhere in the fleet. Correctly
declined to add a new formula-based generator rather than repeat it. **Flagged for whoever owns the J
pipeline decision — this is a cross-cutting, fleet-wide problem, not fixable per-county.**

All 3 leads' claims were independently re-run from scratch by a separate refuter agent (not trusting any
pasted numbers) and survived: REAL for B/F and I, honest-FAIL-confirmed for C/D/G, and
NO_CHANGE_CLAIMED/honest-BLOCKED-confirmed for J. Full evidence logged to `gold_standard_ultraloop_audit`
(7 new rows, all `survived=true` meaning the *characterization* — PASS or honest FAIL — was verified
accurate, not that every letter passes).

## SQL VERIFICATION

```sql
-- run 2026-07-20T21:2x UTC, live via mgmt_sql.py (Management API)

-- volusia BEFORE (stale, fabricated)
-- A pass(94) B pass(100) C pass(98.1) D pass(98.9) E pass(100) F pass(100)
-- G pass(100, FABRICATED) H pass(5.5) I pass(98.4, FABRICATED) J pass(100)  -- 10/10 displayed, not certified

select public.pencil_dod_evaluate_county('volusia');  -- AFTER
-- A pass(94) B pass(100) C pass(98.1,366) D pass(98.9,369) E pass(100,373) F pass(100,175/175)
-- G FAIL(null) H pass(5.9) I FAIL(0.0, card_complete=0 of 373) J pass(100,373)  -- 8/10, honest

select public.pencil_dod_evaluate_county('union');
-- A pass(1) B FAIL(null,0/0) C pass(100,3) D pass(100,3) E pass(100,3) F FAIL(null,0/0)
-- G pass(100) H pass(8.9) I pass(100,3/3) J pass(100,3)  -- 8/10, unchanged, zero drift

-- sarasota BEFORE (this session's start)
-- A pass(93) B FAIL(22.0,22/100) C FAIL(10.0,34) D FAIL(10.0,34) E pass(95.3,325)
-- F FAIL(22.0,22/100) G FAIL(null) H pass(5.4) I FAIL(0.0,0/341) J FAIL(0.0)  -- 3/10 (A,E,H)

select public.pencil_dod_evaluate_county('sarasota');  -- AFTER
-- A pass(93,fc=93 td=248) B pass(98.3,verified=119 closed_sold=121)
-- C FAIL(37.2,matched_clean=127) D FAIL(37.2,matched_any=127) E pass(95.3,325)
-- F pass(98.3,tier1_sold=119 closed_sold=121) G FAIL(0,density=0.0 far=0.0 pk1000=0.0)
-- H pass(0.1) I FAIL(41.9,card_complete=143 of 341) J FAIL(0.0)  -- 5/10 (A,B,E,F,H)

select id, county_slug, letter, survived from gold_standard_ultraloop_audit
  where dispatch_id = '95aa6180-826c-4bd0-8442-58da4023282d' order by id;
-- 10 rows: volusia G/I (survived=false, ghost-success confirmed+purged), union B (survived=false,
-- structural block reconfirmed), sarasota B/C/D/F/G/I/J (survived=true, characterization verified accurate)
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were not run (other shards were
concurrently mid-flight — a sibling shard's gadsden/walton/hillsborough/calhoun commits landed on `main`
during this session's rebase) — per-county `pencil_dod_evaluate_county` was used for all verification
instead.

## Migrations shipped (all applied live + committed to main, no side branches)

1. `migrations/20260720_gold_standard_shard6_run5361_volusia_g_i_ghost_success_purge.sql` (`a7d923b6`)
2. `migrations/20260720_gold_standard_shard6_run5361_sarasota_bcdf_realtaxdeed_realforeclose.sql` (`8ca5328a`, documentation-only — the actual writes were live REST calls from two committed Python scripts, verified byte-for-byte against the DB by the refuter)
3. `migrations/20260720_gold_standard_shard6_run5361_sarasota_g_i_zoning_real_gis.sql` (`8d5baaa8`)

## Next-session priorities

1. **sarasota C/D**: needs either the 190 tax_deed sales to actually occur (mostly future-dated/redeemed —
   time-gated, not a bug) or a scoring-methodology decision on excluding cancelled/redeemed rows from scope.
2. **sarasota G**: needs real `zone_standards` (max_far/max_density_du_acre/parking_per_1000sf) for
   jurisdictions 824 (Sarasota) and 941 (North Port) — real zoning *codes* now exist (this session), only the
   numeric ordinance values are missing. Venice (933) still needs a real parcel-to-zone match (point-in-polygon
   tax-account mismatch this session) before its 28 untrusted zone_standards rows are worth trusting.
3. **sarasota J**: do NOT attempt a per-county formula-based generator — this session confirmed the entire
   fleet-wide J-generator script family (30 scripts, including at least one currently `survived=true` letter
   elsewhere in the fleet, lee id=7908) uses hardcoded fixed-ratio ml_score/CMA formulas. This needs a real
   ML-scoring/real-comps pipeline decision made once, fleet-wide, not per-county improvisation.
4. **union B/F**: nothing to do until `63-2025-CA-0053` closes 2026-08-13.
5. **Fleet-wide flag (not this shard's authority)**: the "(Beta Synthetic)"/"(ShardN Synthetic)" zoning
   fabrication pattern found in volusia this session also exists, unpurged, in at least 10 other counties'
   `zoning_districts` (ids listed in Part 1) — flagged for their owning shards, same as this campaign's
   existing cross-shard-flag precedent.

---
dispatch_id: 95aa6180-826c-4bd0-8442-58da4023282d
