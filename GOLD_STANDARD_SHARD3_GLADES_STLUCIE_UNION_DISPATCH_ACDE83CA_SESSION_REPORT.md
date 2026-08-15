# Gold Standard shard-3: glades, st_lucie, union — session report

dispatch_id: `acde83ca-0ef2-4df1-b907-e6ae224b191a` · GitHub issue #19105 · session: architect-20260815T160000

Run via the Workflow tool (ultracode explicitly requested this session): one ULTRALOOP pipeline, 4 targets,
each with an independent fix agent followed by an independent adversarial-refuter agent (8 agents total,
~761K subagent tokens, 322 tool calls, ~18 min wall-clock). Orchestrating session did recon (confirmed
psql is broken — password auth failure, confirmed `supabase` CLI is not installed, confirmed live evaluator
baselines for all 3 counties, read the prior lee/st_lucie/taylor and glades-2nd-firing session reports to
avoid re-deriving already-settled diagnoses) before dispatching the workflow, then ran final live
verification and this close-out after it returned.

## Scoreboard

| County | Before | After | Delta |
|---|---|---|---|
| glades | 9/10 (J fail 65.7%) | 9/10 (J fail 94.1%) | J moved 65.7%→94.1%, 1 row short of PASS — no letter flip, large honest gain |
| st_lucie | 8/10 (C, I fail) | 9/10 (C fail, **I now PASS**) | **I flipped FAIL→PASS** (53.8%→95.0%) |
| union | 6/10 (B,C,D,F fail) | 6/10 (unchanged) | Reconfirmed genuinely blocked, 6th consecutive independent session to reach this conclusion |

## st_lucie I — 53.8% → 95.0% (FAIL → PASS), the session's headline result

**Root cause (already correctly scoped by yesterday's lee/st_lucie/taylor report, not re-derived):** E
(parcel linkage) already passed at 95.5% (211/221 rows have `parcel_id`), but I additionally requires that
`parcel_id` resolve a `zone_code` via `v_zoning_gold_standard_card`, which joins through `public.parcel_zones`.
The ~92-row gap was pure `parcel_zones` coverage — not a linkage bug.

**Fix:** discovered live ArcGIS zoning endpoints for all 3 St Lucie jurisdictions that needed them (Port St
Lucie, Fort Pierce, unincorporated St Lucie County GIS) via each entity's own DCAT feed, then ran the same
spatial-point-query methodology already proven for indian_river
(`supabase/migrations/20260813_shard3_indian_river_i_zone_linkage.sql`) against all 87 gap parcels that had
existing lat/lon, plus 5 more that were geocoded fresh via the free US Census geocoder. 91 of 92 gap parcels
resolved to a real, spatially-confirmed zone_code; 1 was honestly left unlinked (a stale "PID Gone" parcel
record with an ambiguous double-hit in the source GIS layer — not forced).

**Caught and fixed a live regression before it shipped:** the 91 new (jurisdiction, zone_code) pairs
introduced 12 codes with no `zoning_districts` row, which the card view's applicability heuristic defaults
to `far_regulated`/`pk1000_regulated=true` for commercial/industrial codes — this crashed G (a
previously-passing letter) from 96.0% to 0.0%. Fixed by creating the 12 missing `zoning_districts` rows:
real ordinance-sourced density figures for the 5 residential codes, and explicit
`far_regulated=false, pk1000_regulated=false, density_regulated=false` for the 7 non-residential/PUD codes
(no fabricated FAR/parking numbers). G re-verified at 95.0% (a small net change from 96.0%, still PASS, no
regression) after the fix.

**Migration:** `supabase/migrations/20260815_shard3_stlucie_i_g_zoning_backfill_acde83ca.sql`, commit
`a64bd476`, pushed to main.

**Adversarial verify — SURVIVED.** Independent refuter re-ran the live evaluator (exact match on all 10
letters), spot-checked 3 of the 91 new `parcel_zones` rows by independently re-querying the same live
ArcGIS endpoints at the same lat/lon and got identical zone codes back (one cross-confirmed via the source's
own `Parcel_num` field), reconciled the row-count arithmetic (91 actual inserts vs. the 210-119=91 metric
gain), and confirmed no regression on any other letter or sibling county. One non-blocking finding: the
migration file's own comment-block arithmetic is internally inconsistent (states "86 direct + 5 geocoded"
vs. the actual 86-row `VALUES` list = 91 total; states "10 unresolved" in one place vs. "6" elsewhere) —
flagged as sloppy narrative bookkeeping, not a data-integrity issue; no purge was warranted or performed.

**Honest residual (11/221 rows):** 10 structurally blocked (no address/parcel_id at all — out of scope for
a GIS-only backfill) + 1 stale "PID Gone" parcel.

## glades J — 65.7% → 94.1% (still FAIL, 1 row short, large honest gain)

**Root cause:** the 67 pre-existing `bid_decisions` rows (proven real in a prior firing, pipeline_version
`glades_j_real_comps_v1`/`glades_j_vacant_land_comps_v1`/`glades_j_countywide_comps_v1`) were untouched and
correct — glades' `auctions_total` simply grew from 70 to 102 (32 new tax-deed auctions, mostly a
2026-06-04 batch) since the last J session, mechanically dropping the metric with zero regression in the
underlying data.

**Fix:** reused the exact proven 4-tier real-comps cascade (median/p25/p75 of actual `fl_parcels.sale_prc1`
sales via dash-stripped parcel_id join, `n_comps>=3` required — same methodology as the 3 prior legitimate
migrations, explicitly did NOT touch the two quarantined flat-formula generators) against the 35 new gap
rows. 33/35 joined `fl_parcels`; 29 of those cleared `n_comps>=3` at some tier. Inserted 29 new
`bid_decisions` rows (`pipeline_version='glades_j_countywide_comps_v2_run_acde83ca'`).

**Migration:** `supabase/migrations/20260815_gold_standard_shard3_glades_j_countywide_comps_v2_run_acde83ca.sql`,
commit `ea961d5b`, pushed to main.

**Adversarial verify — SURVIVED.** Independent refuter re-ran the live evaluator (exact match: 96/102,
94.1%), independently recomputed the smallest comp pool (case `TD-2022-44-20260604`, n=3) directly from raw
`fl_parcels` and got an exact match to the stored `p25`/`p75` values, and explicitly re-checked all four
documented ghost-success signatures for this twice-fabricated county — none present (18 distinct `ml_score`
values, 0 flat-multiplier hits, 0 `distress_owner==ml_score` collisions; the single shared batch-insert
timestamp was independently confirmed to be a systemic PostgREST batch-write artifact present in all 3
prior legitimate cohorts too, not a fabrication tell).

**Honest residual (6/102 rows), left BLANK per this county's own hard-learned lesson:**
- `TD-2024-4-20240808`, `222025CA000139CAAXMX` — no `fl_parcels` join possible (same structural E-linkage
  gap flagged in every prior glades J session).
- `TD-2022-6-20240118` (dor_uc=069 agricultural), `TD-2024-36/37/33-20260604` (dor_uc=099) — join fine but
  genuinely `n_comps<3` even at the widest tolerance tier.

J needs 97/102; sits at 96/102. A 7th row requires either fixing the E-linkage gap or new source data —
flagged as next-session priority, not forced.

## union B/C/D/F — reconfirmed genuinely blocked (6th consecutive independent session)

Live-reconfirmed exactly 3 total auctions, 0 closed/sold. Investigated the one actionable case
(`63-2025-CA-0053`, auction date 2026-08-13, 2 days past at session time) against Union's real live source
(`unionclerk.com` via `scripts/clerk_ssot/parsers/union.py`, Playwright): the case is absent from the
rendered HTML entirely, not just the "upcoming" section. New evidence beyond every prior session on this
case: two previously-unread `bctelegraph.com` legal-notice issues confirm a real, court-ordered "Order
Rescheduling Foreclosure Sale dated June 17, 2026" moved the sale to exactly August 13, 2026 — matching our
DB precisely and ruling out stale-scrape as an explanation. Checked both post-sale-date newspaper issues
(8/6, 8/13) — no mention; the next issue (8/20) isn't published yet. No post-sale outcome exists anywhere in
any public source as of this session. Zero fabricated writes made — before/after evaluator JSON is
byte-identical.

**Migration/report:** `GOLD_STANDARD_SHARD3_UNION_DISPATCH_ACDE83CA_SESSION_REPORT.md` (separate file,
committed by the fix agent directly), commit `85b560d7`.

**Adversarial verify — SURVIVED.** Independent refuter re-ran the live evaluator (byte-identical, only
trivial `H` freshness drift from elapsed time), independently re-ran the same Playwright parser (same
result: case absent), independently fetched all 4 cited newspaper URLs (all matched exactly), and confirmed
via direct row fetch that no fabricated write exists in the DB.

## st_lucie C — reconfirmed structural ceiling, correctly not force-fixed

Live-reconfirmed `matched_clean=185/221` (83.7%). Recomputed the evaluator's own filter locally and
reproduced 185/221 exactly. Broke down the 36 excluded rows: 35 `CLERK_SSOT_CANCELLED` + 1 genuinely
`matched_divergent` (case `2025CA001832`, live-reconfirmed via the RealForeclose AJAX calendar as still
returning `parcel_id: 'MULTIPLE PARCELS'` — a genuinely ambiguous source record, not a stale classification).
221 − 35 − 1 = 185 is the actual current ceiling (83.7%), below the 95% pass bar by construction of the
evaluator. No writes made (nothing honestly promotable). Standing recommendation, now repeated by a 3rd+
independent session on this exact letter: escalate to the AI Architect for an evaluator-formula decision on
whether cancelled/multi-parcel rows should be excluded from C's denominator — this is out of a single
county-session's authority.

**Adversarial verify — SURVIVED** for the C claim itself (3x independent live RPC calls, byte-identical).
One minor audit-trail flag (not a data issue): this agent's report happened to paste I's *original dispatch-
brief baseline* (FAIL, 119/221) as background context rather than a fresh live snapshot, and by the time its
sibling agent (st_lucie I, running concurrently in the same pipeline) had already shipped the real I fix,
that pasted number was stale relative to the final merged state. The refuter correctly flagged this as a
narrative-precision nit — no DB write was made or needed on this agent's part, and I's real live state
(95.0% PASS) is exactly as reported in the st_lucie I section above.

## ULTRALOOP audit trail

4 pipeline items, all 4 claims independently adversarially verified and SURVIVED (no purges required this
session — a first for a session touching glades J, which has been fabricated and purged twice before).
Audit rows written to `gold_standard_ultraloop_audit` (`dispatch_id=acde83ca-...`, `ultraloop_mode=native`)
by each refuter agent directly via PostgREST for county_slug ∈ {st_lucie, union, glades} covering letters
I, G, C (st_lucie), B/C/D/F (union), J (glades).

## Verification protocol followed

- `pencil_dod_evaluate_county` run before and after every change, all 3 counties — pasted above and
  independently re-confirmed live by the orchestrating session after the workflow returned (all numbers
  match exactly).
- Did not run `gold_standard_loop()` or `gold_standard_certify()` — other shards pushed to main concurrently
  during this session (visible in `git log`: shard-1 sumter/brevard, shard-2 charlotte/bradford/liberty/
  hernando, shard-4 madison/bay, holmes, hernando — all landed on main during this session's window). Used
  per-county `pencil_dod_evaluate_county` throughout, per PARALLEL-FLEET RULES.
- `gold_standard_campaign` close-out row (id=4421, dispatch_id=acde83ca-...) updated with per-county
  `criteria_passed` JSON and `exit_reason='timeout'`.
- All git pushes used `git pull --rebase` first; all rebases resolved cleanly against concurrent shard
  activity (confirmed via clean working tree post-session).

## Next-session priorities for glades / st_lucie / union

1. **glades J**: 96/102 (94.1%), 1 row short of the 97-row PASS bar. Two sub-populations remain: (a) 2 rows
   with no `fl_parcels` join at all (same E-linkage gap flagged repeatedly) — fixing E's parcel-join for
   these 2 specific cases would likely flip J to PASS; (b) 4 rows with genuinely thin comp pools even at
   the widest tolerance tier — no honest lever without new source data. Try (a) first next session.
2. **st_lucie C**: reconfirmed hard ceiling at 83.7-84.5% (34-35 cancelled + 1 genuinely ambiguous
   multi-parcel row), well below the 95% bar by the evaluator's own design. 3rd+ independent session to
   reach this exact conclusion — escalate to the AI Architect for a canon exception on cancelled-row
   denominator handling rather than attempting a 4th data-harvesting pass.
3. **union B/C/D/F**: still blocked. Case `63-2025-CA-0053`'s next possible public data point is the
   `bctelegraph.com` 8/20 issue (not yet published at session time) or a future Civitek OCRS unlock. No
   further action possible until new source data appears — do not re-investigate before a genuinely new
   lever (new newspaper issue, clerk site update) exists.
4. **st_lucie I residual (11 rows)**: 10 structurally blocked (no address/parcel_id), 1 stale "PID Gone"
   parcel — both genuine data gaps, not mechanically closable this cycle.
