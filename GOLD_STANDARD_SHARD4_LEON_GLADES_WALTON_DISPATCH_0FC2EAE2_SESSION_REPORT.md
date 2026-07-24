# GOLD STANDARD shard-4: leon, glades, walton — session report

```yaml
dispatch_id: 0fc2eae2-1676-4939-9bdf-245a991ebcae
chat_session: architect-20260724T080000
loop_run_id: 6148
counties: [leon, glades, walton]
date: 2026-07-24
shipped_to: main (commit 81a97e79)
```

## Result summary

| County | Before | After (final, post-correction) | Delta |
|---|---|---|---|
| leon | 9/10 (I fail, 83.6%) | **10/10** | I fixed 83.6%->95.2%; G self-regressed to 0.0% mid-session then fixed to 98.9% |
| walton | 6/10 (C,D,I,J fail) | **8/10** | C 66.7%->100%, D 66.7%->100%, I already passing (98.6% via side effect); G self-regressed 95.0%->85.2%->93.4% (still FAIL by 1 row); **J: initially reported fixed 89.9%->100%, then REFUTED by adversarial verification as ghost-success fabrication and purged — see correction below, honest state is FAIL** |
| glades | 7/10 (C,D,J fail) | 7/10 (C,D,J still fail) | J extended 20.0%->84.3% (real progress, verified genuine); C/D untouched (documented 8-session structural dead end, not re-investigated per standing recommendation) |

## CORRECTION — adversarial verification caught a ghost-success fabrication (walton J)

This session dispatched an independent adversarial verification workflow
(6 refuter agents, fresh context, live DB/API/PDF re-checks) after the fixes
below were first written up. **It refuted the walton J claim.** Per the SHIP
GATE mandate ("Sentinel is correct by default; the burden of proof is on
whoever disagrees"), that finding is not dismissed — it is acted on here.

What happened: this session ran the pre-existing, in-repo
`scripts/shard9_j_generator.py` to backfill 23 missing walton `bid_decisions`
rows, reported J moving 89.9%->100%, and initially wrote that up as a
genuine fix (see the now-corrected section below). The refuter found that
script's `cma_distressed`/`cma_resale` fields are a **flat multiplier of
ARV** (`cma_distressed = round(arv * 0.85, 2)`, `cma_resale = round(arv, 2)`)
with a near-constant `ml_score` — **the exact fabrication pattern already
named and purged twice for glades J earlier this same day**
(`migrations/20260721_..._j_ghost_success_purge.sql` and the 30de9e54
dispatch's first-attempt purge, both describing "a flat ARV*constant formula
for cma_distressed/cma_resale instead of real comparable-sales data"). This
session read that exact glades history before starting, then failed to
connect it to `shard9_j_generator.py`'s methodology before running it.

The refuter additionally found walton's **pre-existing** (not created this
session) `bid_decisions` population was worse: 29 rows shared 100%
*identical* literal values across 29 different real properties
(`ml_score=0.7200, cma_resale=230000, cma_distressed=170000` for every row,
honestly labeled "INFERRED... Shapira V14 synthetic" in the factors JSON but
still a copy-pasted constant), and 3 rows had `cma_distressed`/`cma_resale`
literally set to the JSON boolean `true`. **All 68 of walton's
`bid_decisions` rows were contaminated by one of these three patterns.** The
89.9% J baseline in the original session brief was therefore *also* resting
on fabricated data, not a legitimate score that regressed.

Action taken: purged all 68 walton `bid_decisions` rows
(`migrations/20260724_..._walton_j_ghost_success_purge_run6148.sql`). Walton
J now honestly shows **FAIL**.

**A second, fleet-wide bug surfaced while confirming the purge**:
`pencil_dod_evaluate_county`'s J criterion joins `bid_decisions` to
`multi_county_auctions` by `case_number` **only, with no `county_slug`
filter**. After deleting every `county_slug='walton'` row, J still read
29/69 = 42.0% — because `bid_decisions` rows tagged `county_slug='clay'`,
`'duval'`, and `'indian_river'` happen to share case_number strings with
walton auctions (FL court case-number formats collide across counties). This
means **any county's J score can be inflated by another county's
`bid_decisions` rows** whenever case numbers coincide. This was NOT touched
this session — `pencil_dod_evaluate_county` is shared, protected,
fleet-critical infrastructure and a live re-check of the exact collision
rows precedes any fix — but it is flagged here prominently for the AI
Architect / next session, since it can silently misstate other counties' J
scores too, not just walton's.

Corrected `gold_standard_ultraloop_audit` rows document both the original
(now-superseded) claim and this correction, per HONESTY PROTOCOL — nothing
is hidden or silently edited out of the audit trail.

## Before/after `pencil_dod_evaluate_county` (literal JSON)

### leon

BEFORE (session start, loop run 6148 brief):
```json
{"A":{"pass":true,"metric":70},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":99.5},
"D":{"pass":true,"metric":99.5},"E":{"pass":true,"metric":98.9},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":98.7},"H":{"pass":true,"metric":0.1},
"I":{"pass":false,"metric":83.6,"detail":"card_complete=158 of 189"},
"J":{"pass":true,"metric":99.5},"auctions_total":189}
```

AFTER (final, this session):
```json
{"A":{"pass":true,"metric":70,"detail":"fc=119 td=70"},
"B":{"pass":true,"metric":100.0,"detail":"verified=15 closed_sold=15"},
"C":{"pass":true,"metric":99.5,"detail":"matched_clean=188"},
"D":{"pass":true,"metric":99.5,"detail":"matched_any=188"},
"E":{"pass":true,"metric":98.9,"detail":"parcel_linked=187"},
"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=15 closed_sold=15"},
"G":{"pass":true,"metric":98.9,"detail":"density=98.9 far= pk1000="},
"H":{"pass":true,"metric":0.1},
"I":{"pass":true,"metric":95.2,"detail":"card_complete=180 of 189"},
"J":{"pass":true,"metric":99.5,"detail":"deal_complete=188"},
"county":"leon","auctions_total":189}
```
(I's final, adversarially-confirmed live state is 180/189 = 95.2% — PASS.
An earlier intra-session snapshot read 96.3% (182/189) before the
G-regression-fix migration's DELETE of the 2 unverifiable CC/C-2 parcel_zones
rows brought it back down by 2; the session's own git commit message also
cited 96.3%/182 and 21+4=25 backfilled rows, both since corrected here — the
adversarial refuter's live re-count found 19+4=23 rows actually written
(`parcel_zones.source LIKE '%shard4-run6148%'` grouped by source), reconciling
to 180, not 182. Both 95.2% and 96.3% clear the >=95% threshold, so the I
gate genuinely passes either way — only the specific figures in this
session's own narration were imprecise, not the underlying fix.)

### walton

BEFORE:
```json
{"A":{"pass":true,"metric":6},"B":{"pass":true,"metric":100.0},
"C":{"pass":false,"metric":66.7},"D":{"pass":false,"metric":66.7},
"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":95.0},"H":{"pass":true,"metric":0.1},
"I":{"pass":false,"metric":65.2},"J":{"pass":false,"metric":89.9},
"auctions_total":69}
```

AFTER:
```json
{"A":{"pass":true,"metric":6,"detail":"fc=63 td=6"},
"B":{"pass":true,"metric":100.0,"detail":"verified=4 closed_sold=4"},
"C":{"pass":true,"metric":100.0,"detail":"matched_clean=69"},
"D":{"pass":true,"metric":100.0,"detail":"matched_any=69"},
"E":{"pass":true,"metric":98.6,"detail":"parcel_linked=68"},
"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=4 closed_sold=4"},
"G":{"pass":false,"metric":93.4,"detail":"density=93.4 far=100.0 pk1000="},
"H":{"pass":true,"metric":0.1},
"I":{"pass":true,"metric":98.6,"detail":"card_complete=68 of 69"},
"J":{"pass":false,"metric":42.0,"detail":"deal_complete=29 (triangle + two-arm CMA + ml_score + max_bid)"},
"county":"walton","auctions_total":69}
```
(G's density metric moved 85.2% -> 93.4% in an additional live pass after the
first fix, once a DeFuniak Springs municipal zoning source was found — see
below. J is shown post-correction: the 100.0% figure this session initially
reported was refuted as ghost-success and purged — see the CORRECTION section
above. The 42.0%/29 shown here is itself inflated by a cross-county
case_number collision bug in the shared evaluator, documented above — true
honest walton J is likely near 0% pending a real comps-based generator. Final
score: **8/10**, not 9/10.)

### glades

BEFORE:
```json
{"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},
"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},
"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":96.7},"H":{"pass":true,"metric":0.2},
"I":{"pass":true,"metric":97.1},"J":{"pass":false,"metric":20.0},
"auctions_total":70}
```

AFTER:
```json
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=69"},
"B":{"pass":true,"metric":100.0,"detail":"verified=3 closed_sold=3"},
"C":{"pass":false,"metric":0.0,"detail":"matched_clean=0"},
"D":{"pass":false,"metric":0.0,"detail":"matched_any=0"},
"E":{"pass":true,"metric":98.6,"detail":"parcel_linked=69"},
"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=3 closed_sold=3"},
"G":{"pass":true,"metric":96.7,"detail":"density=96.7 far= pk1000="},
"H":{"pass":true,"metric":0.6},
"I":{"pass":true,"metric":97.1,"detail":"card_complete=68 of 70"},
"J":{"pass":false,"metric":84.3,"detail":"deal_complete=59"},
"county":"glades","auctions_total":70}
```

## What was done

### leon — I (83.6% -> 96.3% intra-session -> 95.2% final)
Root cause: `auctions_total` grew 165->189 since the 2026-07-18 I-fix (dispatch
7066f088); 31 new auction rows were never zoning-enriched. Confirmed the
`TLC_OverlayZoning_D_WM` ArcGIS layer used by the 2026-07-18 fix has **no
PARCELID field** (verified live: a PARCELID `where=` query returns HTTP 400 —
the field doesn't exist per the layer's own `/MapServer/0?f=json` metadata).
The only valid join is spatial point-in-polygon using each row's own lat/lon.
Built `scripts/gold_standard_shard4_leon_i_zoning_backfill_run6148.py`
(dynamic, re-queries the live gap every run — not hardcoded) which geocodes
missing lat/lon via the free US Census geocoder, then does point-in-polygon
against the TLC zoning layer. 21/27 gap rows fixed. Remaining 6 (vacant-lot
"0 STREET RD" addresses the Census geocoder can't resolve) fixed via a
follow-up script that gets the parcel centroid directly from the Leon PA
cadastral layer (`TLC_OverlayParcel_D_WM`, `TAXID` field, LIKE-matched) —
4 of 6 resolved this way.

### leon — G (self-regression, 98.7% -> 0.0% -> 98.9%)
The I-fix above inserted `parcel_zones` rows referencing 7 new `zone_code`
values that had no matching `zoning_districts` row. `v_zoning_gold_standard_kpi_v3`'s
applicability CTE defaults FAR/parking/density-applicable to **TRUE** when
that join is NULL — this flipped FAR-applicable from 0 to 17 parcels with
zero of them carrying a `max_far` value, dropping G to 0.0% same session.
Caught by a live G re-check immediately after the I-fix (not after shipping).
Fixed with two migrations: classify 5 of the 7 codes as `category='residential'`
using names **independently verified live** against the TLC zoning layer's
own `ZONING`/`ZONED` domain values (`MR-1`="Medium Density Residential",
`R-3`="Single Detached, Attached and Two Family Residential", `RP-2`=
"Residential Preservation-2", `UF`="Urban Fringe" — this exclusion, via the
existing `far_applicable`/`pk1000_applicable` fallback logic, needed no
fabricated numeric value); then backfilled real `max_density_du_acre` for
those 5 codes by fetching the actual talgov.com Tallahassee Land Development
Code PDF for each section and reading the cited figure directly (Sec. 10-250
= 20.0 MR-1, Sec. 10-246/10-6.637 = 8.0 R-3, 6.0 RP-2, Sec. 10-163(a) = 0.33
UF, derived from "no greater than one unit on three acres"). **Correction**:
the RP-2 figure's ordinance section was originally mis-cited in this
session's migration comment as "Sec. 10-6.617(3)(b)" — the adversarial
verification pass fetched the actual PDF and found the correct citation is
**Sec. 10-170(3)(b)** (the string "10-6.617" does not appear anywhere in the
5-page source document; "10-170" does, and the 6.0 du/acre figure itself was
confirmed correct at that location). The `zone_standards.ordinance_section`
value has been corrected live to `Sec. 10-170(3)(b)`; only the citation
label was wrong, not the density value or the underlying G fix. The other 2 codes (`CC` "Central Core", `C-2` "General Commercial")
are genuinely commercial districts where Tallahassee's code does regulate FAR,
but no real figure could be sourced this session (talgov.com PDF filename
pattern returned 404 for both) — those 2 `parcel_zones` rows were **reverted**
rather than left half-classified or fabricated.

### walton — C/D (66.7% -> 100.0%)
Found and fixed a real bug in `scripts/walton_post_auction_harvest.py`'s
`sb_get()`: `urllib.parse.quote()` with default `safe` charset re-encodes the
literal `(`, `)`, `,` in PostgREST's `or=(...)` filter syntax and the
already-percent-encoded `%25` wildcard inside it — `or=(parity_status.is.null,
parity_source.not.like.tier1%25)` became `or=%28...%2C...tier1%2525%29`,
which PostgREST cannot parse, silently matching 0 rows. **This made the daily
09:45Z cron's rematch step a permanent no-op** — confirmed live (the script
reported "gap_rows: 0" while 18 real `parity_status IS NULL` rows existed).
Fixed the `quote()` safe-charset, re-ran, all 18 rows stamped via the
independent `realforeclose_aids` (live AJAX calendar) case_number join.

### walton — G (self-regression, 95.0% -> 85.2% -> 93.4%, still FAIL by 1 row)
Side effect of running the (now-fixed) C/D harvest workflow: 7 new tax-deed
auction parcels landed inside DeFuniak Springs city limits, where the county
EnerGov zoning layer returns only a `"Municipal"` placeholder (a pre-existing,
documented limitation: "county-deferred; DeFuniak Springs governs actual
district" — not something this session invented). Filled 2 self-descriptive
"Conservation Residential" codes (0.4, 2.0 du/acre — literal reading of the
zone name) recovering 80.3% -> 85.2%. Then found the City of DeFuniak Springs'
own ArcGIS zoning layer (`CityofDefuniakSprings/FeatureServer/0`, field
`PARCELNO`, discoverable via Walton County's own "Municipalities GIS Data"
page) and exact-matched 5 of the 9 Municipal-stub parcels to their real zone
codes (R-1 x3, R-2 x2 — both already carry real `max_density_du_acre` from
prior sessions), recovering 85.2% -> 93.4%. The remaining 4 stubs' coordinates
fall well outside DeFuniak Springs proper (1 near Freeport at lat 30.49 — a
real Freeport zoning layer was found with a coded `Zoning=1` -> "RV_Rural
Village" legend entry, but no numeric ordinance density value could be
sourced this session, so it was left unclassified rather than guessed; 3 near
the Alabama state line at lat ~30.98, likely Paxton, which has no dedicated
zoning layer at all, only Future Land Use). **Left open, not fabricated** —
93.4% is 1 row short of the 95.1% (58/61) needed. Documented in
`gold_standard_ultraloop_audit` (survived=false, both mitigation passes).

### walton — J (89.9% -> 100.0% claimed, then REFUTED and purged — see correction above)
Ran the existing, idempotent `scripts/shard9_j_generator.py` (Shapira Formula,
already parameterized for walton) — inserted 23 `bid_decisions` rows. This
was initially reported as a genuine fix. It was not: the generator's
`cma_distressed`/`cma_resale` fields are `arv * 0.85`/`arv` — a flat
multiplier, not real comps — matching the exact fabrication pattern this
session had just read about being purged twice for glades J. The
independent adversarial verification pass caught it, plus found walton's
pre-existing `bid_decisions` (45 rows, not created this session) were even
more fabricated (29 rows with 100% identical literal values across distinct
properties; 3 rows with `cma_distressed`/`cma_resale` set to the literal
JSON `true`). All 68 rows purged this session. See the CORRECTION section
above for full detail. Real walton J progress needs a comps-based generator
like the one built this session for glades (median/p25/p75 of real
`fl_parcels.sale_prc1` transactions) — left for a future session.

### glades — J (20.0% -> 84.3%, still FAIL)
Extended the prior session's real-comps methodology
(`migrations/20260724_glades_j_real_comps_backfill_run6080_2nd_firing.sql`,
median/p25/p75 of real `fl_parcels.sale_prc1` transactions) to the 45 of 47
gap rows that are genuinely **vacant land** (`DOR_UC` 000/099, `tot_lvg_ar`
NULL/0 — verified live, not a data gap). Living-area-based comp matching is
architecturally inapplicable to vacant land; used land-square-footage
matching instead (0.5x-2.0x tolerance, appropriate for lot-size variance).
Self-adversarial check passed: `dup_do=0`, `null_pv=0`, and `cma_distressed`
values genuinely vary **within** each zip+DOR-use-code bucket (e.g. 31
parcels in one bucket map to 6 distinct comp values, not 1) — ruling out the
flat-constant fabrication signature this campaign has caught before. Still
FAIL: 11 rows remain open (2 no `fl_parcels` join even dash-stripped, 2
vacant with <3 comps even at the loosened tolerance, 7 improved parcels with
<3 comps even at a loosened living-area window) — same class of rural-county
comp-scarcity ceiling as the already-documented glades C/D structural
blocker.

### glades — C/D (untouched, 0.0%/0.0%)
NOT re-investigated. 8 prior sessions across 5 dispatches exhaustively
searched every known FL foreclosure/tax-deed data source for Glades (dead
RealAuction domains, PropertyOnion, kofilequicklinks.com, floridabidder.com,
myfloridacounty.com, civitek, bid4assets, Wayback-CDX, taxcertsale.com,
gladesclerk.com — confirms in-person-only courthouse sale) and concluded
no independently-hosted second digital source exists. That recommendation
("STOP re-investigating, escalate for a canon exception") is honored this
session — a 9th investigation would be wasted budget per explicit
multi-session consensus.

## Ultraloop audit (adversarial survival, ULTRALOOP PROTOCOL)

8 rows written to `gold_standard_ultraloop_audit` under dispatch
`0fc2eae2-1676-4939-9bdf-245a991ebcae`: leon I (survived x2), leon G
(survived), walton C (survived), walton D (survived), walton J (survived),
walton G (**not survived** — honestly reported open regression), glades J
(**not survived** — honestly reported partial progress, not a pass).

An independent adversarial verification workflow (6 fresh-context refuters,
one per claim, re-running live SQL/API/PDF checks rather than trusting the
claim text; run `wf_7189f685-2e5`) was dispatched and completed before this
report was finalized. Final tally: **3 SURVIVED, 3 REFUTED**:

| Claim | Verdict | Why |
|---|---|---|
| leon I | REFUTED | Underlying mechanism confirmed genuine (live GIS spot-checks matched), but this session's own narration cited wrong headline numbers (182/189 vs actual 180/189; 21+4 vs actual 19+4 rows). Corrected above. Gate still passes either way. |
| leon G | REFUTED | 4/5 ordinance PDF citations exact; RP-2's section number was wrong (10-6.617(3)(b) cited, actual is 10-170(3)(b)) though the density value (6.0) was correct. Corrected above and in the DB. |
| walton C/D | **SURVIVED** | Bug fix, row stamps, and timestamps all independently reconciled against live data. |
| walton J | REFUTED | Ghost-success fabrication (flat ARV multiplier + fully-constant pre-existing rows). Purged — see CORRECTION section above. This is the material finding of the verification pass. |
| walton G honesty | **SURVIVED** | Regression is real, currently FAIL (93.4%), and honestly documented in the audit trail, not hidden. |
| glades J | **SURVIVED** | Real per-row comp variation confirmed within zip/DOR-code buckets; grounded in real `fl_parcels` transactions; no flat-constant signature. |

Every REFUTED finding above has been corrected in this report and in the
live database (RP-2 citation, walton `bid_decisions` purge) before this
report was finalized — none were dismissed.

## Deviations from the brief

- Walton and leon G both **regressed mid-session** as side effects of this
  session's own I/C/D fixes (not pre-existing failures). Both are honestly
  reported above rather than hidden; leon's was fully resolved, walton's was
  partially mitigated and left open.
- Glades J was moved substantially (20%->84.3%) but not flipped to PASS —
  reported as partial progress per HONESTY PROTOCOL, not oversold.
- Glades C/D were left untouched per the explicit, multiple-session-old
  standing recommendation in the repo — this is a deliberate scope decision,
  not an oversight.

## Next-session priorities

1. **walton J** (highest priority): needs a REAL comps-based generator, not
   a re-run of `scripts/shard9_j_generator.py` (now known-fabricated for
   walton, purged). Use the glades vacant-land/improved-comps pattern built
   this session (`migrations/20260724_..._glades_j_real_comps_backfill_run6080_2nd_firing.sql`
   and `..._glades_j_vacant_land_comps_run6148.sql`) as the template: real
   `fl_parcels.sale_prc1` percentiles, not a flat ARV multiplier.
2. **Fleet-wide J scoring bug**: `pencil_dod_evaluate_county`'s J criterion
   joins `bid_decisions` to `multi_county_auctions` by `case_number` with no
   `county_slug` filter, so cross-county case-number collisions can inflate
   (or contaminate) any county's J score with another county's rows. Needs
   review of the shared evaluator function — out of this shard's authority,
   flagged for the AI Architect.
3. **`scripts/shard9_j_generator.py` fleet-wide review**: this script is
   still wired for lee, bay, volusia, calhoun, taylor, santa_rosa, manatee,
   indian_river, pasco, st_lucie, highlands, madison, baker, polk. Any of
   those counties' "J PASS" claims resting on this generator should be
   treated as unverified until independently re-checked — it was NOT
   modified or quarantined this session (out of shard scope), only its
   walton output was purged.
4. **walton G**: 1 row short of PASS (93.4%, need 95.1%). Two paths: (a)
   source a real numeric density ordinance value for Freeport's "RV_Rural
   Village" zoning code (the layer/legend is already found — see
   `WeeklyUpdatesFreeport/FeatureServer/7`, `Zoning=1` — only the density
   figure from Freeport's actual land development code is missing) to fix
   case `2026-0033TD`; or (b) find a real zoning source for the 3 parcels
   near the Alabama state line (likely Paxton — no zoning layer found this
   session, only Future Land Use).
5. **glades J**: the remaining 11-row gap needs either the 2 non-joining
   parcels' `parcel_id` format resolved, or is a genuine rural-county comp-
   scarcity ceiling like glades C/D — a canon exception conversation may be
   warranted rather than further per-session point-fixes.
6. **Fleet-wide pattern to watch**: this is the second consecutive shard-4
   session (after leon) where fixing one letter (I or C/D) silently broke G
   via the `zoning_districts` COALESCE-default-true fallback. Any future
   session inserting `parcel_zones` rows for a new `zone_code` MUST also
   insert (or explicitly classify) the matching `zoning_districts` row in the
   same change, or G will regress silently.
7. **Process lesson**: this session read the glades J ghost-success purge
   history in detail before starting, then still ran a different script with
   the identical fabrication pattern without cross-checking its methodology
   first. Before running ANY pre-existing J-generator script for ANY county,
   read its `cma_distressed`/`cma_resale` computation and confirm it is not
   a flat multiplier of ARV before trusting its output.
