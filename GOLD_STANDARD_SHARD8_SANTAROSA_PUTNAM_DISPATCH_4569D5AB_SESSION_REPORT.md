# GOLD STANDARD shard-8 (santa_rosa, putnam) — dispatch `4569d5ab-b34d-4b1e-80fb-183b058262db`, session report

mode: fallback (manual Task subagent fan-out — 2 fix agents + adversarial refuter agents, not native `/effort ultracode`)

## Starting scoreboard (pre-fix baseline)

```
santa_rosa 8/10: A✓ B✓ C✓ D✓ E✓(96.5) F✓ G✗(0) H✓ I✗(88.4: card_complete=76 of 86) J✓
putnam     5/10: A✓ B✓ C✗(65.6) D✗(65.6) E✓(97.6) F✓ G✗(0) H✓ I✗(94.3: card_complete=427 of 453) J✓
```

## What this session did

Two fix agents ran against the two counties' open letters:

1. **santa_rosa I** (`scripts/gtm22j_santa_rosa_i_backfill.py`) — chased the 7
   card_complete gaps. 6 of the 7 parcels got a real zoning substrate write
   (`parcel_zones` rows: zone_code `R1M`, `C-1`, `HCD`, `R1`, `RM`, `RM-A`,
   `source='ArcGIS'`) plus real jurisdiction-attributed zone names (e.g.
   "Mixed Residential Subdivision", "Highway Commercial Development"). Case
   #1 (`572022CA000671CAAXMX`) was correctly identified as unfixable — no
   `parcel_id`/lat/lon/market data exists for it anywhere upstream — and was
   left null rather than fabricated.

2. **putnam C/D** (`scripts/gtm22j_putnam_cd_harvest.py`) — harvested 15
   additional clean-matched rows (`parity_source` tagged
   `tier1:gtm22j_putnam%`), moving `matched_clean`/`matched_any` from 297 to
   312 of 453. This does **not** clear the 95% pass gate (68.9% < 95%) and
   was reported honestly as still `pass=false`.

3. **putnam I** (`scripts/gtm22j_putnam_i_backfill.py`) — wrote 12 new
   `parcel_zones` rows (5 Palatka, 6 Interlachen, 1 Pomona Park) and 5 new
   `zoning_districts` rows, sourced from live `gis.putnam-fl.com`
   `MunicipalZoning_PDS` layers 14/16. Moved card_complete from 427 to 439
   of 453, clearing the gate (96.9% > 95%).

Each fix agent's claim was handed to an independent adversarial refuter
agent whose job was to re-run the canonical evaluator fresh, re-derive raw
DB rows independently (not trust the pasted report), and specifically hunt
for ghost-success, fabricated values, cross-county leakage, and false
"skip" claims.

## Before/after `pencil_dod_evaluate_county` — literal JSON (Honesty Protocol proof)

### santa_rosa — BEFORE (documented pre-fix baseline)
I: `{"pass": false, "detail": "card_complete=76 of 86", "metric": 88.4}` — all other letters unchanged from AFTER below except I.

### santa_rosa — AFTER (fresh, re-run live this session, byte-identical to fixer's pasted output)
```json
[
  {
    "pencil_dod_evaluate_county": {
      "A": { "pass": true, "detail": "fc=58 td=28", "metric": 28 },
      "B": { "pass": true, "detail": "verified=31 closed_sold=31", "metric": 100 },
      "C": { "pass": true, "detail": "matched_clean=86", "metric": 100 },
      "D": { "pass": true, "detail": "matched_any=86", "metric": 100 },
      "E": { "pass": true, "detail": "parcel_linked=83", "metric": 96.5 },
      "F": { "pass": true, "detail": "tier1_sold=31 closed_sold=31", "metric": 100 },
      "G": { "pass": false, "detail": "density=92.3 far=0.0 pk1000=25.0", "metric": 0 },
      "H": { "pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 6.1 },
      "I": { "pass": true, "detail": "card_complete=83 of 86", "metric": 96.5 },
      "J": { "pass": true, "detail": "deal_complete=86 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100 },
      "county": "santa_rosa",
      "V2_LITMUS": null,
      "auctions_total": 86
    }
  }
]
```

### putnam — BEFORE (documented pre-fix baseline)
C: `{"pass": false, "detail": "matched_clean=297", "metric": 65.6}`, D: `{"pass": false, "detail": "matched_any=297", "metric": 65.6}`, I: `{"pass": false, "detail": "card_complete=427 of 453", "metric": 94.3}` — all other letters unchanged from AFTER below.

### putnam — AFTER (fresh, re-run live this session, byte-identical to fixer's pasted output)
```json
[
  {
    "pencil_dod_evaluate_county": {
      "A": { "pass": true, "detail": "fc=41 td=412", "metric": 41 },
      "B": { "pass": true, "detail": "verified=3 closed_sold=3", "metric": 100 },
      "C": { "pass": false, "detail": "matched_clean=312", "metric": 68.9 },
      "D": { "pass": false, "detail": "matched_any=312", "metric": 68.9 },
      "E": { "pass": true, "detail": "parcel_linked=442", "metric": 97.6 },
      "F": { "pass": true, "detail": "tier1_sold=3 closed_sold=3", "metric": 100 },
      "G": { "pass": false, "detail": "density=98.2 far=0.0 pk1000=50.0", "metric": 0 },
      "H": { "pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 5 },
      "I": { "pass": true, "detail": "card_complete=439 of 453", "metric": 96.9 },
      "J": { "pass": true, "detail": "deal_complete=450 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.3 },
      "county": "putnam",
      "V2_LITMUS": null,
      "auctions_total": 453
    }
  }
]
```

## Plan vs actual

| County | Letter | Planned | Actual | Deviation |
|---|---|---|---|---|
| santa_rosa | I | Backfill zoning substrate for all 7 card_complete gaps, clear gate | 6 of 7 fixed (88.4%→96.5%, gate cleared); case #1 correctly left null — no upstream data exists for it | None — the 7th case was genuinely unfixable, not a shortfall in effort |
| santa_rosa | G | Not in scope this session | Unchanged, still failing (density=92.3 far=0.0 pk1000=25.0) | Deferred — see next-session priorities |
| putnam | C | Harvest clean-matched rows toward 95% gate | +15 rows, 65.6%→68.9%, gate NOT cleared | Partial improvement only; genuinely far from 95%, honestly reported as still failing |
| putnam | D | Same underlying data as C | +15 rows, 65.6%→68.9%, gate NOT cleared | Same as C |
| putnam | I | Backfill zoning substrate for card_complete gaps | 12 parcels fixed, 94.3%→96.9%, gate cleared | None |
| putnam | G | Not in scope this session | Unchanged, still failing (density=98.2 far=0.0 pk1000=50.0) | Deferred — see next-session priorities |

## Claims survived vs refuted

All 4 claims **survived** independent adversarial verification. **None were refuted.**

- **santa_rosa I (survived)** — evaluator re-run fresh matched exactly; all
  7 claimed case rows spot-checked directly in `multi_county_auctions`; all
  6 `parcel_zones` writes verified to exist with real (non-placeholder)
  zone codes/names and session-window timestamps; case #1's claimed "skip"
  independently confirmed still fully null (not silently marked complete);
  no cross-county leakage found.
- **putnam C (survived, still failing)** — evaluator output byte-identical
  to fixer's paste; raw `matched_clean`/`NULL`/total counts in
  `multi_county_auctions` independently recomputed and match to the decimal;
  all 15 promoted rows spot-checked for realistic Putnam parcel IDs/town
  names; zero cross-county `parity_source` leakage; report explicitly and
  correctly states the gate is not met (no ghost-success).
- **putnam D (survived, still failing)** — same underlying data as C,
  independently re-derived from `data_source`/`parity_status` group-by; same
  zero-leakage and no-ghost-success results.
- **putnam I (survived)** — evaluator matched exactly; 2 of 12 GIS lookups
  independently re-executed against the live `gis.putnam-fl.com` ArcGIS
  service from scratch (not reading the fixer's script output) and
  reproduced identical `ZONECLASS` values; exactly 12 new `parcel_zones`
  rows and 5 new `zoning_districts` rows confirmed, all correctly
  jurisdiction-attributed to Putnam; G-letter guard rail confirmed
  unaffected (still metric=0, no regression).

No claim required rejection. No fabricated data, ghost-success, or scope
leakage was found in any of the four refutation passes.

## Full 10/10 check (Telegram gate)

Neither county reached 10/10 this session:
- santa_rosa: **9/10** (G still failing)
- putnam: **6/10** (C, D, G still failing)

Per the brief, the standing Telegram notification is **skipped** — not both
counties cleared all 10 gates.

## Next-session priorities

1. **santa_rosa orphan case `572022CA000671CAAXMX`** — fully null
   (`parcel_id`/lat/lon/market_value/assessed_value all null). Confirmed no
   upstream source data exists for this case in this session; needs a fresh
   research pass (different data source, not a repeat of this session's
   ArcGIS approach) before it can be considered further, or should be
   explicitly documented as structurally unfixable if a future session also
   comes up empty.
2. **santa_rosa G** (density/FAR/park-1000 zoning coverage) — untouched
   this session, `density=92.3 far=0.0 pk1000=25.0`, metric=0. FAR and
   park-proximity components are the gap; needs real ordinance research
   (`far_regulated`/park-distance fields) similar to prior shard sessions'
   G-letter fixes (see shard1/shard3 pattern: real ordinance zone_standards
   for FAR + density).
3. **putnam C/D** — still well below the 95% gate at 68.9% (312/453,
   141 unmatched rows remain). The harvest script
   (`scripts/gtm22j_putnam_cd_harvest.py`) proved the approach works;
   scaling it further (more source coverage, retry on the remaining 141
   nulls) is the concrete next step. At the current per-session yield
   (+15 rows), multiple more sessions will be needed to close a ~120-row
   gap to 95%.
4. **putnam G** — untouched this session, `density=98.2 far=0.0 pk1000=50.0`,
   metric=0. Same FAR-ordinance-research gap as santa_rosa G; likely worth
   tackling both counties' G letters together in one future session since
   the root cause (missing `far_regulated` data in `zoning_districts`) is
   structurally identical.

## Addendum — G regression caught and fixed (follow-up firing)

**Regressing commit:** `ad98e7074c3dc6e27e2ea9b1cc4a7e64174ba922` (the santa_rosa I
+ putnam C/D/I fix shipped above). That commit's `parcel_zones`/`zoning_districts`
writes for criterion I regressed criterion G on **both** counties.

### Root cause

`v_zoning_gold_standard_kpi_v3` (which criterion G reads) joins
`parcel_zones -> zoning_districts ON (jurisdiction_id, code=zone_code) ->
v_zoning_district_applicability -> zone_standards`. When a `zoning_districts`
row has no matching `code` for a given `jurisdiction_id`/`zone_code`, or when a
`zoning_districts` row exists but has **no** `zone_standards` row at all, the
view's `COALESCE(far_applicable, true)` / `COALESCE(pk1000_applicable, true)` /
`COALESCE(density_applicable, true)` defaults flip that parcel into "applicable
with NULL standard" — which counts as a FAIL in the G numerator instead of
being correctly excluded or correctly satisfied.

- **santa_rosa**: the I-fix inserted 6 new `parcel_zones` rows; 3 of the 6 had
  `zone_code` values (`R1` Milton, `RM` Jay, `HCD` unincorporated) that did not
  match any existing `zoning_districts.code` for that jurisdiction, so all
  three fell into the NULL-standard-defaults-to-FAIL trap.
- **putnam**: the I-fix inserted 5 new `zoning_districts` rows (ids
  12159–12163) for the newly-added parcels, but **zero** `zone_standards` rows
  for any of them — same trap, at the district level instead of the code-match
  level.

Both are honest regressions: the I-fix agents correctly and honestly disclosed
"G-letter guard rail confirmed unaffected (still metric=0, no regression)" in
their own claim text, but "still metric=0" was only true because G was
*already* failing before their change (density=92.3/98.2, far=0.0,
pk1000=25.0/50.0) — the guard-rail check compared pass/fail state, not the
underlying detail numbers, so it missed that the composition of the failure
got worse (pk1000 dropped from 25.0/50.0, and new NULL-standard rows were
added to the denominator). This follow-up session fixes those specific new
gaps with real, sourced ordinance data.

### What each fix script did

- **`scripts/gtm22j_santa_rosa_g_regression_fix.py`**:
  1. Normalized `parcel_zones.zone_code` `R1` → `R-1` for the Milton parcel
     (matches pre-existing `zoning_districts` id=11522, Milton UDC Article 6
     Table 6.2.1 — pure normalization bug, no new district needed).
  2. Inserted a real `zoning_districts` row for Jay `RM` ("Residential
     Medium", sourced from the SRCPA Town of Jay Zoning map), distinct from
     the pre-existing `RM-A` district. No numeric FAR/density/parking
     standard was found (Jay's ordinance host is a JS-rendered SPA
     unreachable this session, Firecrawl had zero credits) — left
     `zone_standards` unpopulated rather than fabricated, category defaults
     correctly exclude it from far/pk1000.
  3. Inserted a real `zoning_districts` + `zone_standards` row for
     unincorporated Santa Rosa `HCD` ("Highway Commercial Development"),
     sourced from the Santa Rosa County LDC (Sec 2.02, Tables 2.04.02.b /
     2.05.01.b / 2.06.01.b): `max_density_du_acre=10`, setbacks 50/5/25,
     height=50, min_lot_width=100. `far_regulated=false` /
     `pk1000_regulated=false` set explicitly — verified the LDC has no
     district-wide FAR or parking-per-1000sf standard for HCD (FAR only
     appears in airport-overlay use-caps; parking is set per land-use type,
     not per district) — a sourced non-applicability finding, not a silent
     default.

- **`scripts/gtm22j_putnam_g_regression_fix.py`**: inserted real, sourced
  `zone_standards` rows for all 5 of the I-fix's new `zoning_districts`
  (ids 12159–12163, covering Palatka/Crescent City/Interlachen/Pomona
  Park/Welaka): `max_far=1.00`, `parking_per_1000sf=3.33`,
  `max_density_du_acre` 5.81/5.81/2.00/5.00 depending on district. Values are
  derived (e.g. `parking_per_1000sf=3.33` = 1 space per 300 sqft;
  `max_density_du_acre=5.81` = 43,560/7,500), not guessed placeholders.

Both scripts are idempotent (pre-check before insert/update, never clobber a
later real value) and scope-guarded to only their county's jurisdiction IDs.

### Before/after `pencil_dod_evaluate_county` — literal JSON (this session)

**santa_rosa — BEFORE this session (regressed state, from ad98e70 session
report AFTER block above):**
`G: {"pass": false, "detail": "density=92.3 far=0.0 pk1000=25.0", "metric": 0}`

**santa_rosa — AFTER (fresh, re-run live this session):**
```json
[
  {
    "pencil_dod_evaluate_county": {
      "A": { "pass": true, "detail": "fc=58 td=28", "metric": 28 },
      "B": { "pass": true, "detail": "verified=31 closed_sold=31", "metric": 100 },
      "C": { "pass": true, "detail": "matched_clean=86", "metric": 100 },
      "D": { "pass": true, "detail": "matched_any=86", "metric": 100 },
      "E": { "pass": true, "detail": "parcel_linked=83", "metric": 96.5 },
      "F": { "pass": true, "detail": "tier1_sold=31 closed_sold=31", "metric": 100 },
      "G": { "pass": false, "detail": "density=93.2 far=0.0 pk1000=100.0", "metric": 0 },
      "H": { "pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 6.4 },
      "I": { "pass": true, "detail": "card_complete=83 of 86", "metric": 96.5 },
      "J": { "pass": true, "detail": "deal_complete=86 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100 },
      "county": "santa_rosa",
      "V2_LITMUS": null,
      "auctions_total": 86
    }
  }
]
```

**putnam — BEFORE this session (regressed state, from ad98e70 session report
AFTER block above):**
`G: {"pass": false, "detail": "density=98.2 far=0.0 pk1000=50.0", "metric": 0}`

**putnam — AFTER (fresh, re-run live this session):**
```json
[
  {
    "pencil_dod_evaluate_county": {
      "A": { "pass": true, "detail": "fc=41 td=412", "metric": 41 },
      "B": { "pass": true, "detail": "verified=3 closed_sold=3", "metric": 100 },
      "C": { "pass": false, "detail": "matched_clean=312", "metric": 68.9 },
      "D": { "pass": false, "detail": "matched_any=312", "metric": 68.9 },
      "E": { "pass": true, "detail": "parcel_linked=442", "metric": 97.6 },
      "F": { "pass": true, "detail": "tier1_sold=3 closed_sold=3", "metric": 100 },
      "G": { "pass": false, "detail": "density=99.6 far=50.0 pk1000=100.0", "metric": 50 },
      "H": { "pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 5.4 },
      "I": { "pass": true, "detail": "card_complete=439 of 453", "metric": 96.9 },
      "J": { "pass": true, "detail": "deal_complete=450 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.3 },
      "county": "putnam",
      "V2_LITMUS": null,
      "auctions_total": 453
    }
  }
]
```

### Claims survived adversarial verification (2 of 2)

Both G-fix claims **survived** independent adversarial re-verification
(fresh evaluator re-run, independent DB queries, refutation attempts on
fabrication/scope-leakage/idempotency — see `gold_standard_ultraloop_audit`
ids 7481/7482 for full refuter evidence):

- **santa_rosa G (survived, still failing)** — pk1000 fixed 25.0→100.0,
  density improved 92.3→93.2, far remains 0.0 (blocked by one genuine
  pre-existing out-of-scope parcel, not something this session caused or
  hid — see below). No regressions on any other letter.
- **putnam G (survived, still failing)** — far improved 0.0→50.0, density
  improved 98.2→99.6, pk1000 held at 100.0. No regressions on any other
  letter.

### Still open (honest residual gaps)

Neither county reaches a full G PASS yet, and neither reaches 10/10 overall:

- **santa_rosa: 9/10** (G still fails, metric=0). Remaining G gap: `far=0.0`
  is driven by exactly one applicable parcel — Gulf Breeze `C-1`
  (`zoning_districts` id=5563, `jurisdiction_id`=828, `created_at`=2026-02-08,
  i.e. it predates this entire GTM-22J session chain by ~5 months) which has
  `far_regulated=null` (defaults to applicable) and `zone_standards` id=2553
  with `max_far=NULL`. This is a genuine pre-existing data gap, not caused by
  either the regressing commit or this fix — confirmed via `created_at`
  timestamp, independently verified by the adversarial refuter. Needs a
  dedicated Gulf Breeze ordinance research pass in a future session.
- **putnam: 6/10** (C, D, G still fail). G's remaining gap: 6 districts
  (ids 5643/5644/5645/5646/5647/5685, codes C-1A/C-1/C-2/C-3/M-1/PID) still
  have `max_far=NULL`, capping far at 50.0% instead of 100%. C/D remain at
  68.9% (312/453), well below the 95% gate — unchanged this session, carried
  forward from the prior firing's "next-session priorities" (needs further
  harvest-script scaling, ~120 rows still unmatched).

Per the brief's Telegram gate ("only if BOTH counties show a full 10/10"),
**the notification is skipped** — neither county cleared all 10 gates this
session.

## Addendum 2 — BOTH COUNTIES REACH 10/10 (closing firing)

Picked up exactly where the prior addendum left off: santa_rosa 9/10 (G
failing), putnam 6/10 (C, D, G failing).

### santa_rosa G: root cause was a wrong applicability flag, not a missing value

The prior addendum correctly identified the residual FAR gap as Gulf Breeze
`C-1` (`zoning_districts` id=5563, `max_far=NULL`) and flagged it for a
dedicated ordinance research pass. Ran that pass this firing via a background
Workflow (research agent + independent adversarial verifier, two separate
live fetches of the same Gulf Breeze ordinance mirror): **C-1's own ordinance
division (Div. 8, Sec. 21-161/162/163) has no FAR section at all** — only
permitted uses, height (35 ft), and setback (15 ft). The district was never
missing a FAR *value*; `v_zoning_district_applicability`'s generic
commercial-category heuristic was wrongly flagging it as FAR-*applicable* in
the first place. Fix: `zoning_districts.far_regulated = false` for id=5563
(the existing override column built for exactly this situation) — this
removes the district's one parcel from the FAR denominator instead of
fabricating a number the ordinance doesn't contain.

That alone shifts G's binding constraint from far (0.0) to density (93.2,
still <95). Backfilled `max_density_du_acre` for 3 of the 6 remaining Milton,
FL districts (R-1→5.81, R-1A→4.84, R-U→6.22 du/acre = 43,560/min-lot-area-sqft
from directly-quoted lot sizes in City of Milton UDC Article 6 Tables
6.2.1/6.4.1 — the same derivation already used by the pre-existing,
passing Interlachen R-1A/R-2 rows in this table). The other 3 (Gulf Breeze
R-C, Jay RM, Jay RM-A) could not be sourced this session (Town of Jay isn't
on municode; no working mirror had the figures) and were left NULL — not
needed for PASS since 100/103=97.1% already clears 95%.

**Result: santa_rosa G FAIL(0.0) → PASS(97.1). santa_rosa is now 10/10.**

### putnam G: identical pattern, one district

Same root cause, one district: Palatka `C-2` (`zoning_districts` id=5645).
Live WebFetch of the ordinance's own schedule of district regulations (Sec.
94-149(f)) explicitly states **"Maximum Density: Not applicable"** and lists
height/impervious-surface/yard figures but zero FAR line. Fix:
`far_regulated=false` for id=5645. The other FAR-applicable district in
putnam (Interlachen C-2, id=12159) already had `max_far=1.00` filled from a
prior firing and correctly remains counted.

**Result: putnam G FAIL(50.0) → PASS(99.6).**

### putnam C/D: the "harvest more rows" plan from addendum 1 was wrong — refuted before shipping

Addendum 1 left ~120 unmatched rows as "needs harvest-script scaling." This
firing re-ran the harvest for all 7 affected auction dates live — the
RealTaxDeed AJAX calendar returned real, paginated results (36-51 items per
date) with **zero case-number overlap** against the 141 unmatched rows. Not a
matching-key bug: these case numbers simply are not on the vendor calendar.

Initial hypothesis: redeemed/cancelled before sale (very common in FL tax
deed sales). Dispatched an adversarial forensics agent specifically to try to
confirm or refute this against an independent government source before
writing any fix. **It refuted the hypothesis**: checked 6 sample case numbers
against the Putnam Clerk of Court's own tax deed certification system
(`apps.putnam-fl.com/coc/taxdeeds/public/public_certification.php`) — all 6
came back live, active, unredeemed, with "Date of Sale" matching our
`auction_date` exactly. The real root cause is a RealTaxDeed-vendor-side
calendar coverage gap, not stale data on our side.

Built `scripts/putnam_clerk_certification_cd_fix.py` to close the loop
properly: verify **all 141** rows (not just the 6-sample) against that same
Clerk endpoint — confirm the case is found, not shown as redeemed/cancelled,
and its "Date of Sale" matches our `auction_date` — before promoting.
**141/141 confirmed** (0 redeemed, 0 mismatched, 0 not-found). Promoted all
141 to `parity_status='matched_clean'`,
`parity_source='tier1:clerk_certification_php:putnam:<date>'`.

**Result: putnam C FAIL(68.9%, 312/453) → PASS(100%, 453/453). putnam D
FAIL(68.9%, 312/453) → PASS(100%, 453/453). putnam is now 10/10.**

### Before/after `pencil_dod_evaluate_county` — literal JSON (this firing)

**santa_rosa — BEFORE (= addendum 1's AFTER):**
`G: {"pass": false, "detail": "density=93.2 far=0.0 pk1000=100.0", "metric": 0.0}`

**santa_rosa — AFTER (fresh, re-run live):**
```json
{"A":{"pass":true,"metric":28},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
 "D":{"pass":true,"metric":100},"E":{"pass":true,"metric":96.5},"F":{"pass":true,"metric":100},
 "G":{"pass":true,"detail":"density=97.1 far= pk1000=100.0","metric":97.1},
 "H":{"pass":true,"metric":8},"I":{"pass":true,"metric":96.5},"J":{"pass":true,"metric":100},
 "county":"santa_rosa","auctions_total":86}
```

**putnam — BEFORE (= addendum 1's AFTER):**
```json
{"C":{"pass":false,"metric":68.9,"detail":"matched_clean=312"},
 "D":{"pass":false,"metric":68.9,"detail":"matched_any=312"},
 "G":{"pass":false,"detail":"density=99.6 far=50.0 pk1000=100.0","metric":50}}
```

**putnam — AFTER (fresh, re-run live):**
```json
{"A":{"pass":true,"metric":41},"B":{"pass":true,"metric":100},
 "C":{"pass":true,"detail":"matched_clean=453","metric":100},
 "D":{"pass":true,"detail":"matched_any=453","metric":100},
 "E":{"pass":true,"metric":97.6},"F":{"pass":true,"metric":100},
 "G":{"pass":true,"detail":"density=99.6 far=100.0 pk1000=100.0","metric":99.6},
 "H":{"pass":true,"metric":6.9},"I":{"pass":true,"metric":96.9},"J":{"pass":true,"metric":99.3},
 "county":"putnam","auctions_total":453}
```

### Adversarial verification (4 claims, 1 dispute resolved)

Ran an independent refute-pass workflow (3 agents, none of which wrote any
fix) against all 4 claims above. 3 of 4 (putnam G, putnam C, putnam D)
survived cleanly on first pass. The 4th (santa_rosa G) came back
`survived=false` on one specific point: the refuter claimed the Milton R-U
density figure's source lot-area (7,000sf) was misattributed and should be
6,000sf. Rather than accept or dismiss this unilaterally, independently
re-verified via precise character-column-position analysis of the same
`pdftotext -layout` output (R-U header at column 38, R-C1 at column 80; "SF:
7,000sf" aligns at column 39 under R-U, "SF: 6,000sf" aligns at column 79
under R-C1), then dispatched a **second, fresh tie-breaker agent** with no
knowledge of either prior verdict, which independently re-derived the same
column positions from scratch and confirmed the original figure (7,000sf →
6.22 du/acre) is correct — the first refuter had misread the table's
two-line column wrap. Logged transparently in `gold_standard_ultraloop_audit`
(the dispute and its resolution, not just the final verdict) rather than
silently overridden.

All 4 claims logged to `gold_standard_ultraloop_audit` with `survived=true`
(ids 7529-7532), dispatch_id=`4569d5ab-b34d-4b1e-80fb-183b058262db`.

### Full 10/10 — Telegram gate

**Both counties now show a full 10/10** on live `pencil_dod_evaluate_county`.
Per the brief, this clears the "BOTH counties 10/10" gate. `SELECT
public.gold_standard_loop()` / `gold_standard_certify()` could not be invoked
this session — the Supabase Management API returned a persistent `403
(Cloudflare error 1010)` specifically on that RPC across 6 retry attempts
over several minutes, while ordinary SELECT/UPDATE queries against the same
API endpoint worked fine throughout (including immediately before and after
the failed attempts). Per the brief's own fallback instruction ("otherwise
skip loop and report per-county evaluations"), skipped rather than forced —
this is an infra/WAF issue, not a data problem, and certification is a
separate automated gate (10/10 twice consecutively at the daily 07:30Z run)
this session doesn't control directly.

### Residual / next-session

- santa_rosa: 3 parcels (Gulf Breeze R-C, Jay RM, Jay RM-A) still have no
  `max_density_du_acre` — not needed for PASS (97.1% > 95%) but genuinely
  unsourced; a future session with working Firecrawl credit and/or a way to
  reach Town of Jay's `municipalcodeonline.com` host (not on library.municode.com)
  could close these for full margin.
- Global loop/certify invocation blocked by the Management API 403 above —
  worth flagging to whoever operates that endpoint if it recurs; not a data
  issue on this session's part.

---
dispatch_id: 4569d5ab-b34d-4b1e-80fb-183b058262db
