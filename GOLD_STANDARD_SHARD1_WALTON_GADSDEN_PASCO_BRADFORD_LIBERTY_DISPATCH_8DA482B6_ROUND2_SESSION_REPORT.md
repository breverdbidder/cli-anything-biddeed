# Gold Standard shard-1 — walton, gadsden, pasco, bradford, liberty — round 2

dispatch_id: 8da482b6-8cff-45ea-9950-4e8fed552f37 · session 2026-08-27 (continuation, later same day)

This is the second round of work on this dispatch today. Round 1 (commits `a7a66a3d`, `ddd3cd69`)
already fixed gadsden J and pasco B, partially remediated pasco G, reconfirmed liberty A and bradford
B/F as genuine ceilings, refreshed walton's stale audit rows, and re-flagged walton J as ghost-fill
(survived=false). This round used an ULTRALOOP fix+adversarial-verify workflow (3 tracks, 6 agents) to
close the two remaining tractable gaps (pasco G, walton J) and re-verify gadsden C with a live source
check, rather than re-running a generic sweep across letters already known to be genuine ceilings.

## Live state (`pencil_dod_evaluate_county`, before this round → after, independently re-queried)

```
walton:   10/10 unchanged (A=49 B=100.0 C=99.4 D=99.4 E=96.8 F=100.0 G=98.0 H=0.1 I=95.5 J=99.4)
          — but J's audit trail moved from survived=false (ghost-fill) to survived=true (real fix).
gadsden:  9/10 unchanged  (C fails at 85.1%, matched_clean=57/67) — reconfirmed canon-block, not a bug.
pasco:    9/10 -> 10/10   G: 50.0 (fail, density=94.6 far=50.0 pk1000=50.0)
                             -> 95.4 (pass, density=95.4 far=100.0 pk1000=100.0)
bradford: 8/10 unchanged  (B, F null — reconfirmed dead this morning, no new lever, not re-polled again)
liberty:  7/10 unchanged  (A, B, F fail — reconfirmed dead this morning, no new lever, not re-polled)
```

## pasco G — REAL FIX, PASS (commit `7d37c6e2`)

Three residual `parcel_zones` rows (id 872463 jurisdiction 1258 Unincorporated Pasco; ids 872475/872476
jurisdiction 811 City of Zephyrhills) all carried `zone_code='ZH'` with no matching real
`zoning_districts` row, left open by the prior partial fix (`20260827e_..._partial_fix_8da482b6.sql`).

Live research (Pasco BOCC Zoning ArcGIS MapServer `ZN_TYPE` renderer at
`mapping.pascopa.com/arcgis/rest/services/Land_Use/MapServer/1`, plus City of Zephyrhills' own official
Jan-2024 zoning map) confirmed `ZH` is one of 6 municipal-jurisdiction placeholder codes on Pasco's
countywide layer (alongside DC/NPR/PR/SA/SL) — a "this parcel is zoned by its own incorporated city, not
the county" marker, not a real zoning district in either system. Unlike the 27 real codes in the same
GIS renderer (each linking to a specific Pasco LDC Ch.500 ordinance page), these 6 have no ordinance
link, and Zephyrhills' own 27-district legend has zero `ZH` entry.

Fix: inserted 2 `zoning_districts` rows (jurisdictions 1258, 811) marking `ZH` explicitly
`far_regulated=false, density_regulated=false, pk1000_regulated=false`, with full sourced documentation.
No FAR/density/parking value was fabricated — this is a confirmed negative (verified non-district), not
a missing-data guess. Migration: `supabase/migrations/20260827g_gold_standard_pasco_g_zh_marker_resolved_8da482b6.sql`.

Result: **G: 50.0 → 95.4, FAIL → PASS**. Independently re-verified live by both the adversarial refuter
agent and this session's own re-query. Pasco is now 10/10 on raw metrics.

## walton J — REAL FIX, ghost-fill eliminated (script `scripts/gs_8da482b6_walton_j_ghostfix.py`)

Commit `ddd3cd69` (earlier today) flagged walton J as ghost-success: 95 of 145 `bid_decisions` rows
shared one of two identical templated tuples (84 rows at arv=$208,000/max_bid=$90,600/ml_score=0.75; 11
rows at arv=$50,000/max_bid=$0/ml_score=0.38) despite J reading PASS live (99.4%).

Root cause (confirmed by reading `scripts/shard9_j_generator.py`, not by guessing): `build_bid_decision()`
computes `arv = max(mkt, config['arv'] * 0.4)`, and walton's `COUNTY_CONFIG['arv']` is a single flat
$520,000 estimate keyed to the pricey 30A beach corridor. `0.4 × 520,000 = 208,000` — a floor far above
the real value of most of walton's actual tax-deed inventory, which is concentrated inland around
DeFuniak Springs. For the 84-row template, every one of those case numbers already had a real
`market_value`/`assessed_value` on file (verified range ~$54K–$223K) that the floor was silently
overriding to an identical $208,000. For the 11-row template, real values have since been backfilled
(range ~$804–$56,013) but the `bid_decisions` rows were stale relative to that newer data.

Fix (walton-scoped, one-off script — `scripts/shard9_j_generator.py` was **not** edited, avoiding any
blast radius on the other 6 counties that share it): for each of the 95 rows, looked up the matching
`multi_county_auctions` row (preferring an exact `parcel_id` match), recomputed
arv/repairs/max_bid/ml_score/factors using the same tiered-repair/Shapira-formula shape but **without**
the `arv_base × 0.4` floor (real `market_value`/`assessed_value`/`po_market_value` used directly when
present; `opening_bid × 1.4` as a documented fallback; no fabricated fallback beyond that), and PATCHed
each row by `id`. Sample: case `2026-0067TD` went from arv=$208,000/max_bid=$90,600 (fake, identical to
83 other rows) to arv=$111,130/max_bid=$26,122 (real, this parcel's actual assessed value).

Result: **95/95 rows resolved, 0 left unresolved.** Independently re-verified live this session: zero
rows remain at either degenerate tuple (`content-range: */0` for both), and exactly 95 rows now carry
`arv_source='shapira_formula_walton_j_ghostfix_8da482b6_real_value'`. J's raw PASS percentage is
unchanged (field-presence metric, not a distinctness metric) but the ghost-fill fabrication pattern that
made the PASS untrustworthy is gone — the ULTRALOOP audit row for walton J flipped from survived=false
to survived=true.

## gadsden C — RECONFIRMED canon-structural-block, plus a new reversion finding (no fix applied)

Live parity_status breakdown: 45 PARITY_OK + 11 matched_clean + 1 CLERK_VERIFIED = 57 passing,
+ 10 CLERK_SSOT_CANCELLED = 67 total. This is the exact same fleet-wide pattern documented earlier today
in `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md` for calhoun/manatee/taylor: C's
canon deliberately excludes `CLERK_SSOT_CANCELLED` from its passing set (only D includes it), and real
FL cancellation/redemption rates structurally cap C below 95% by design, not by data defect. All 10
gadsden rows were independently re-verified live against `gadsdenclerk.com/Tax_deeds/Tax_deeds_files/
sheet001.htm` this session — exact case_number/owner/address match, each with an explicit
"Redeemed [date], $0.00" entry. Full detail and table appended as an addendum to that same finding doc.

**New, separate finding:** this exact gadsden gap was already fixed twice on 2026-08-23 (commits
`001733ea`, `5c7bcebe`), reaching C=100.0%, but was silently reverted by the upstream
`gadsden_clerk_tax_deed` scraper re-run at `2026-08-27T11:25:13Z` (identical `updated_at` across all 10
rows). No fix was re-applied this session — a third reclassification would just be reverted again by the
next scrape cycle. This is now flagged as a recurring-reversion pipeline bug (the scraper needs to
respect or itself write `tier1_tax_deed_outcome` provenance) for the next engineer wave, distinct from
the canon-level C-vs-D design question already escalated to the AI Architect/owner.

No `parity_status`, `sold_amount`, or `parcel_id` was fabricated or changed for gadsden this session.

## bradford / liberty — no new work this round

Both were already reconfirmed as genuine, well-documented structural ceilings earlier today (round 1,
commit `a7a66a3d` + `GOLD_STANDARD_BRADFORD_DISPATCH_8DA482B6_SESSION_REPORT.md`): bradford B/F have zero
independent outcome sources anywhere for the 4 overdue cases (10th+ session to confirm this); liberty A
has zero live listings on the newly-registered libertyclerk.com tax-deed source. Re-polling the same dead
sources again within the same session would add no new evidence, so this round focused entirely on the
two tractable gaps (pasco G, walton J) and the gadsden C re-verification instead.

## ULTRALOOP audit trail

3 claims logged to `gold_standard_ultraloop_audit` (ids 18762–18764, dispatch `8da482b6`,
`ultraloop_mode='native'`), all `survived=true` after independent adversarial re-verification by a
dedicated refuter agent per track (6 agents total: 3 fix + 3 verify). Full per-agent transcripts and
tool-call evidence available in the workflow run (`wf_0dd1120a-f08`).

## Guardrail compliance

- No fabricated zoning standard, market value, case outcome, or parity classification anywhere in this
  round.
- `scripts/shard9_j_generator.py` (shared across 7 counties) was read but not edited — the walton fix is
  a scoped, county-filtered, one-off script.
- `pencil_dod_evaluate_county` was not modified.
- `public.gold_standard_loop()` / `public.gold_standard_certify()` were not invoked — 4 other
  `cc-runner-ghonly.yml` runs were confirmed in-flight via `gh run list` at close-out time.
- PropertyOnion was not used as a data source anywhere in this round.

## Mandatory close-out

`gold_standard_campaign` row (id 5157, dispatch `8da482b6`) updated: `criteria_passed.pasco.G` flipped
`false → true` (pasco now 10/10 raw), `criteria_passed` otherwise unchanged from round 1, `exit_reason`
remains `'timeout'` (work continues in future waves; no county fully certified this session — pasco and
walton are at 10/10 raw metrics but certification also requires `gold_standard_certify()`, which was
correctly skipped this round per PARALLEL-FLEET RULES).

## Recommendation for the next session

1. **pasco and walton are both at 10/10 raw metrics.** Next session (or the next `gold_standard_loop()`
   run when no other shard is mid-flight) should run `gold_standard_certify()` and confirm both clear the
   7-day audit-freshness gate for certification.
2. **gadsden's C reversion bug** (upstream scraper silently undoing a verified `tier1_tax_deed_outcome`
   reclassification) should be fixed at the scraper level, not re-patched per-session — otherwise this
   will keep recurring on gadsden's regular re-scrape cycle.
3. **bradford/liberty B/F** remain genuine ceilings; only new lever identified across all sessions to
   date is a human-solvable Turnstile session against civitekflorida.com/ocrs (bradford) — out of scope
   for automated sessions.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
