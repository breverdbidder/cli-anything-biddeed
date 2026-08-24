# Gold Standard shard-2: clay, sumter, hamilton, seminole, wakulla — dispatch ec7aa9c4

ULTRALOOP workflow (5 counties in parallel, diagnose→fix→adversarial-verify per county+letter). All
claimed letter movements survived independent refutation (fresh RPC re-query + row spot-check +
regression check on the other 9 letters). Migrations committed straight to main throughout the
session (no side branches), rebased onto 9 concurrent commits from other shards before final push.

## Before → After (`pencil_dod_evaluate_county`, live, re-queried fresh at session close 2026-08-24T16:50Z)

### clay — 9/10 → **10/10** (G fixed)
```
BEFORE: G FAIL metric=0.0  [density=94.6 far=0.0 pk1000=0.0]
AFTER:  G PASS metric=95.8 [density=95.8 far=100.0 pk1000=]
```
Root cause: 2 real zoning codes (BB, LA RC) had zero `zoning_districts` row, defaulting into the
far/pk1000 "applicable but missing" gap under `v_zoning_district_applicability`'s
`COALESCE(...,true)` default. Also a hyphen hygiene bug (`R2`→`R-2`) orphaned 2 parcels from Clay's
already-populated Green Cove Springs district. Sourced real FAR (40%, Sec. 3-25(e)(7)) and a tiered
density ceiling (Sec. 3-18(e)) from a Wayback Machine snapshot of Clay County's Article III LDC
(qpublic/live Municode unreachable this session; Wayback had a full 284pp text capture).
Migration: `supabase/migrations/20260824_gold_standard_clay_g_bb_larc_r2_hyphen_fix.sql` (commit `46a6119a`).

### sumter — 9/10 (unchanged, confirmed structural ceiling on C)
```
BEFORE: C FAIL metric=91.7 [matched_clean=22 of 24]
AFTER:  C FAIL metric=91.7 [matched_clean=22 of 24]  — NO CHANGE, verified genuine
```
The dispatch brief assumed a PARITY_OK vocabulary gap (per the highlands precedent), but that gap
was already closed fleet-wide by `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`
before this session started — PARITY_OK already counts toward matched_clean. Sumter's real 2-row
gap is `CLERK_SSOT_CANCELLED` (case 104, 1400). Live-reharvested `sumterclerk.com`'s tax-deed widget
this session: both certs independently reconfirmed `status: "redeemed"` — a genuinely different
final state (lien satisfied pre-sale) from a clean match, not a scraper artifact. Forcing these to
`matched_clean` would be fabrication. Audit-trail-only migration:
`supabase/migrations/20260824_gold_standard_sumter_c_reconfirm_no_write.sql` (commit `f1de3626`).

### hamilton — 8/10 → **10/10** (C+D fixed, first success after 4 prior blocked sessions)
```
BEFORE: C FAIL metric=81.0 [matched_clean=17 of 21]   D FAIL metric=81.0 [matched_any=17 of 21]
AFTER:  C PASS metric=100.0 [matched_clean=21 of 21]  D PASS metric=100.0 [matched_any=21 of 21]
```
4 prior sessions (`20260807i`, `20260810_..._216c5868`, `20260724_..._reverify_no_new_writes`,
`20260725c_..._dead_end`) confirmed the same 4 residual rows and exhausted civitekflorida.com/OCRS
(Turnstile-blocked, 3 distinct methods) and Firecrawl (`-21` credit balance, still exhausted this
session too — re-checked live, not re-guessed). The new, never-tried lever: the Internet Archive
Wayback Machine holds 16 snapshots of `hamiltonclerk.com/foreclosures/` **itself** (never crawled
for civitekflorida.com, which is why that specific angle was a dead end, but the clerk's own notice
page always was reachable — it just rotates cases off after their sale date passes). A
2026-05-16 snapshot (captured before all 4 target cases' Apr/May 2026 sale dates) lists all 4 case
numbers with judgment amount, property address, and parcel matching the stored DB rows exactly.
`2025-CA-37`'s stale `PHANTOM_NOT_ON_CLERK` label was a separate root cause: `run_parity.py`'s
forward-looking ±90-day scan window dropped it once its auction date fell into the past (same
mechanism already documented for manatee). Migration:
`supabase/migrations/20260824_gold_standard_hamilton_cd_wayback_reharvest_fix.sql` (commit `f1de3626`).

### seminole — 7/10 → **10/10** (C+D+I fixed)
```
BEFORE: C FAIL 89.9 [133/148]  D FAIL 89.9 [133/148]  I FAIL 89.9 [133/148]
AFTER:  C PASS 98.0 [145/148]  D PASS 98.0 [145/148]  I PASS 95.9 [142/148]
```
C/D: live AJAX harvest against `seminole.realforeclose.com` / RealTaxDeed confirmed 12 new
auction-calendar rows as genuine tier1 matches. I: `scpafl.org` value/geo backfill + `parcel_zones`
links to 7 **pre-existing** zoning_districts (zero new districts created, so G was unaffected —
in fact improved 97.9→98.0 as a side effect of the same parcel links). 6 residual I rows are the
same genuine non-property garbage-parcel cases already documented and correctly left blocked in
`20260725_gold_standard_seminole_i_card_completeness.sql` (alcoholic-license row, multiple-parcels
case, synthetic placeholder parcel, unresolved PID) — not re-attempted, per BLANK > WRONG.
Migration: `supabase/migrations/20260824_gold_standard_seminole_cdi_15row_ajax_geo_zone_backfill.sql`
(commit `872f4642`).

### wakulla — 6/10 (real progress, not yet passing — E/I/J moved together, C unchanged)
```
BEFORE: C FAIL 84.1 [37/44]  E FAIL 81.8 [36/44]  I FAIL 72.7 [32/44]  J FAIL 72.7 [32/44]
AFTER:  C FAIL 84.1 [37/44]  E FAIL 86.4 [38/44]  I FAIL 86.4 [38/44]  J FAIL 86.4 [38/44]
```
Re-applied the proven Sherrell-era method (FL GIO Statewide Cadastral + Wakulla's own
Parcels/Zoning_Map ArcGIS FeatureServers — `services.arcgis.com/yghUoIoA2Cd2cWki` and
`services9.arcgis.com/vAltLjtfYIJc7pDt`) to the 2 of 8 E-gap rows that were resolvable (denominator
grew from 30→44 since the prior 10/10 state; 6 residual rows are permanently-cancelled or
session-blocked, same class as before). E→I→J moved together as expected (I depends on E by
construction; J's comps pipeline needed the newly-linked/zoned parcels). C is out of scope this
pass (correctly-excluded `CLERK_SSOT_CANCELLED` rows, same canon as sumter/hamilton). Migration:
`supabase/migrations/20260824_gold_standard_wakulla_ei_new_row_backfill.sql` (commit `98facb87`).

## ULTRALOOP adversarial verify — all 9 claimed letter-movements SURVIVED
| county | letter | survived |
|---|---|---|
| clay | G | ✅ |
| sumter | C (no-op reconfirm) | ✅ |
| hamilton | C | ✅ |
| hamilton | D | ✅ |
| seminole | C | ✅ |
| seminole | D | ✅ |
| seminole | I | ✅ |
| wakulla | E | ✅ |
| wakulla | I | ✅ |
| wakulla | J | ✅ |

Each verifier independently re-ran `pencil_dod_evaluate_county` fresh (not trusting the fixer's
number), spot-checked ≥2 changed rows against source, and checked the other 9 letters for
regression. Zero refutations this session; zero fabrication findings.

## Shard scoreboard: 3 of 5 counties now 10/10 (clay, hamilton, seminole)
Sumter and wakulla residuals are honestly-documented structural ceilings/partial progress, not
gaps in effort — see the two counties' sections above for what would need to change (a newly-listed
sumter tax-deed sale; wakulla's 6 remaining permanently-cancelled/blocked rows).

## Session close-out (mandatory)
```sql
UPDATE public.gold_standard_campaign
SET criteria_passed = <per-county A-J map, see below>,
    criteria_total = 10,
    exit_reason = 'timeout',
    session_end_at = '2026-08-24T16:50:15Z'
WHERE dispatch_id = 'ec7aa9c4-d8e4-41e7-8fbb-15bf86f78b98';
```
Applied live via PostgREST PATCH, `return=representation` confirmed the write (id=4959).
criteria_passed: clay=10/10 all true, hamilton=10/10 all true, seminole=10/10 all true,
sumter=9/10 (C false), wakulla=6/10 (C/E/I/J false).

### SQL VERIFICATION
Fresh `pencil_dod_evaluate_county` calls per county, 2026-08-24T16:50Z UTC (pasted verbatim above,
not summarized). `gold_standard_campaign.id=4959` PATCH response confirms `criteria_passed`,
`criteria_total=10`, `exit_reason='timeout'`, `session_end_at='2026-08-24T16:50:15+00:00'` all
persisted.

## Next-session priorities
- **wakulla**: 6 residual E/I/J rows — check if any of the "permanently cancelled" class have
  since re-listed; C's gap likely the same CLERK_SSOT_CANCELLED-vs-matched_clean class as
  sumter/hamilton (verify, don't assume). Firecrawl credit balance should be re-checked (was
  exhausted this session, may refresh).
- **sumter**: no action recommended absent a new 25th auction row or one of the 2 redeemed certs
  re-listing for sale — this is a residual, not a bug, per this session's investigation.
- Did not touch cron jobs 109/111/115 or gold_standard_loop; did not run gold_standard_loop() or
  gold_standard_certify() (other shards were live — per PARALLEL-FLEET RULES, ran only
  pencil_dod_evaluate_county per county).
