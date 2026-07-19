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

---
dispatch_id: 4569d5ab-b34d-4b1e-80fb-183b058262db
